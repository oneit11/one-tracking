from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import desc
from models import db
from models.client import Client
from models.device import Device
from models.request import MaintenanceRequest, SupportTicket
from utils.decorators import client_required
from utils.helpers import save_upload, next_sequence
from services import whatsapp as wa

portal_bp = Blueprint("portal", __name__)


def _my_client():
    if not current_user.client_id:
        return None
    return Client.query.get(current_user.client_id)


@portal_bp.route("/")
@client_required
def dashboard():
    client = _my_client()
    if not client:
        # Do NOT log the user out (that made the portal "open then exit again").
        # Show a friendly page while keeping the session alive.
        return render_template("portal/unlinked.html")

    stats = {
        "devices": Device.query.filter_by(client_id=client.id, active=True).count(),
        "open_requests": MaintenanceRequest.query.filter(
            MaintenanceRequest.client_id == client.id,
            MaintenanceRequest.status.in_(["new", "assigned", "in_progress", "report_ready"])
        ).count(),
        "closed_requests": MaintenanceRequest.query.filter(
            MaintenanceRequest.client_id == client.id,
            MaintenanceRequest.status == "closed"
        ).count(),
        "projects": SupportTicket.query.filter(
            SupportTicket.client_id == client.id,
            SupportTicket.status != "closed",
        ).count(),
    }
    # Only open requests in "recent" — closed ones have their own tab
    recent = MaintenanceRequest.query.filter(
        MaintenanceRequest.client_id == client.id,
        MaintenanceRequest.status.in_(["new", "assigned", "in_progress", "report_ready"]),
    ).order_by(desc(MaintenanceRequest.created_at)).limit(5).all()
    return render_template("portal/dashboard.html", client=client, stats=stats, recent=recent)


@portal_bp.route("/devices")
@client_required
def devices():
    client = _my_client()
    if not client:
        return redirect(url_for("portal.dashboard"))
    devices = Device.query.filter_by(client_id=client.id).order_by(Device.name).all()
    return render_template("portal/devices.html", client=client, devices=devices)


@portal_bp.route("/requests")
@client_required
def requests_list():
    client = _my_client()
    if not client:
        return redirect(url_for("portal.dashboard"))
    show = request.args.get("show", "open")  # open | closed | all
    q = MaintenanceRequest.query.filter_by(client_id=client.id)
    if show == "open":
        q = q.filter(MaintenanceRequest.status.in_(["new", "assigned", "in_progress", "report_ready"]))
    elif show == "closed":
        q = q.filter(MaintenanceRequest.status.in_(["closed", "cancelled"]))
    reqs = q.order_by(desc(MaintenanceRequest.created_at)).all()
    counts = {
        "open": MaintenanceRequest.query.filter(
            MaintenanceRequest.client_id == client.id,
            MaintenanceRequest.status.in_(["new", "assigned", "in_progress", "report_ready"])).count(),
        "closed": MaintenanceRequest.query.filter(
            MaintenanceRequest.client_id == client.id,
            MaintenanceRequest.status.in_(["closed", "cancelled"])).count(),
    }
    return render_template("portal/requests_list.html", client=client,
                           requests=reqs, show=show, counts=counts)


@portal_bp.route("/requests/new", methods=["GET", "POST"])
@client_required
def request_new():
    client = _my_client()
    if not client:
        return redirect(url_for("portal.dashboard"))

    # Credit control: block a new request if the client is over their limit.
    from services.account import can_place_request
    from services.settings_service import get_setting
    allowed, block_msg = can_place_request(client)
    if not allowed:
        flash(block_msg, "danger")
        return render_template("portal/account_blocked.html", client=client,
                               message=block_msg,
                               currency=get_setting("currency", "ج.م"))

    devices = Device.query.filter_by(client_id=client.id, active=True).order_by(Device.name).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        contact_phone = request.form.get("contact_phone", "").strip()
        location = request.form.get("location", "").strip()

        from utils.helpers import is_valid_eg_mobile
        errors = []
        if not title:
            errors.append("نوع المشكلة / عنوان الطلب مطلوب")
        if not description:
            errors.append("وصف المشكلة مطلوب")
        if not location:
            errors.append("العنوان / الموقع مطلوب")
        # phone: fall back to the client's stored number if not provided
        phone = contact_phone or client.phone or client.whatsapp or ""
        if not phone:
            errors.append("رقم الموبايل مطلوب")
        elif not is_valid_eg_mobile(phone):
            errors.append("رقم الموبايل غير صحيح — لازم رقم مصري صحيح مثل 01xxxxxxxxx")
        if errors:
            for e in errors:
                flash(e, "warning")
            return render_template("portal/request_form.html", client=client,
                                   devices=devices, form=request.form)

        req = MaintenanceRequest(
            request_number=next_sequence(MaintenanceRequest, "request_number", "MR"),
            client_id=client.id,
            device_id=int(request.form.get("device_id")) if request.form.get("device_id") else None,
            title=title,
            description=(description + (f"\nالموقع: {location}" if location else "")).strip(),
            priority=request.form.get("priority", "normal"),
            contact_phone=phone,
            created_by=current_user.id,
        )
        if "photo" in request.files and request.files["photo"].filename:
            p = save_upload(request.files["photo"], subfolder="reports", prefix="req_")
            if p:
                req.submitted_photo_url = p
        db.session.add(req)
        db.session.commit()
        wa.notify_request_received(req)
        # In-app notification for admins (drives the bell + sound alert)
        from services.notifications import notify_admins
        notify_admins(
            f"طلب صيانة جديد من العميل {req.request_number}",
            f"{client.company_name} — {req.title}",
            "📥", url_for("admin.request_view", rid=req.id),
        )
        flash(f"تم إرسال طلبك رقم {req.request_number}", "success")
        return redirect(url_for("portal.request_view", rid=req.id))

    return render_template("portal/request_form.html", client=client, devices=devices)


@portal_bp.route("/account")
@client_required
def account():
    """Client-facing statement: charges, payments, running balance."""
    client = _my_client()
    if not client:
        return redirect(url_for("portal.dashboard"))
    from services.settings_service import get_setting
    entries = sorted(client.account_entries, key=lambda e: e.created_at)
    # Build running balance for display
    running = 0.0
    rows = []
    for e in entries:
        running += e.signed_amount
        rows.append({"entry": e, "balance": round(running, 2)})
    rows.reverse()  # newest first
    return render_template(
        "portal/account.html", client=client, rows=rows,
        currency=get_setting("currency", "ج.م"),
        bank_name=get_setting("bank_name", ""),
        bank_account=get_setting("bank_account", ""),
    )


@portal_bp.route("/projects")
@client_required
def projects_list():
    client = _my_client()
    if not client:
        return redirect(url_for("portal.dashboard"))
    projects = SupportTicket.query.filter_by(client_id=client.id)\
        .order_by(desc(SupportTicket.created_at)).all()
    return render_template("portal/projects_list.html", client=client, projects=projects)


@portal_bp.route("/projects/<int:tid>")
@client_required
def project_view(tid):
    client = _my_client()
    if not client:
        return redirect(url_for("portal.dashboard"))
    project = SupportTicket.query.get_or_404(tid)
    if project.client_id != client.id:
        abort(403)
    return render_template("portal/project_view.html", client=client, project=project)


@portal_bp.route("/requests/<int:rid>")
@client_required
def request_view(rid):
    client = _my_client()
    if not client:
        return redirect(url_for("portal.dashboard"))
    req = MaintenanceRequest.query.get_or_404(rid)
    if req.client_id != client.id:
        abort(403)
    # Timeline steps for step-by-step visualization
    steps = [
        {"key": "new", "label": "تم استلام الطلب", "at": req.created_at, "done": True},
        {"key": "assigned", "label": "تعيين فني", "at": req.assigned_at, "done": bool(req.assigned_at)},
        {"key": "in_progress", "label": "قيد التنفيذ", "at": req.started_at, "done": bool(req.started_at)},
        {"key": "report_ready", "label": "التقرير جاهز", "at": req.reported_at, "done": bool(req.reported_at)},
        {"key": "closed", "label": "تم الإغلاق", "at": req.closed_at, "done": bool(req.closed_at)},
    ]
    from services.settings_service import get_setting
    return render_template("portal/request_view.html", client=client, req=req, steps=steps,
                           currency=get_setting("currency", "ج.م"))
