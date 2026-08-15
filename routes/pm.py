from datetime import datetime, timedelta, date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import desc
from models import db
from models.client import Client
from models.device import Device
from models.extras import PMSchedule
from models.request import MaintenanceRequest
from utils.decorators import admin_required
from utils.helpers import next_sequence
from services.audit import log_action

pm_bp = Blueprint("pm", __name__)


@pm_bp.route("/")
@admin_required
def schedules_list():
    schedules = PMSchedule.query.order_by(PMSchedule.next_run).all()
    today = date.today()
    return render_template("admin/pm/list.html", schedules=schedules, today=today)


@pm_bp.route("/new", methods=["GET", "POST"])
@admin_required
def schedule_new():
    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()
    if request.method == "POST":
        first = request.form.get("first_run")
        s = PMSchedule(
            name=request.form.get("name", "").strip(),
            client_id=int(request.form.get("client_id")),
            device_id=int(request.form.get("device_id")) if request.form.get("device_id") else None,
            interval_days=int(request.form.get("interval_days") or 90),
            priority=request.form.get("priority", "normal"),
            description=request.form.get("description", "").strip(),
            next_run=datetime.strptime(first, "%Y-%m-%d").date() if first else date.today(),
        )
        db.session.add(s)
        db.session.commit()
        log_action("pm.created", entity_type="pm_schedule", entity_id=s.id)
        flash("تم إضافة جدول الصيانة الوقائية", "success")
        return redirect(url_for("pm.schedules_list"))
    return render_template("admin/pm/form.html", schedule=None, clients=clients)


@pm_bp.route("/<int:sid>/run", methods=["POST"])
@admin_required
def run_now(sid):
    """Generate a maintenance request from this schedule now."""
    s = PMSchedule.query.get_or_404(sid)
    if not s.active:
        flash("الجدول معطّل", "warning")
        return redirect(url_for("pm.schedules_list"))

    from services import whatsapp as wa
    req = MaintenanceRequest(
        request_number=next_sequence(MaintenanceRequest, "request_number", "MR"),
        client_id=s.client_id,
        device_id=s.device_id,
        title=f"صيانة وقائية: {s.name}",
        description=s.description or "توليد تلقائي من جدول الصيانة الوقائية",
        priority=s.priority,
        created_by=current_user.id,
    )
    db.session.add(req)
    s.last_run = date.today()
    s.next_run = s.last_run + timedelta(days=s.interval_days)
    db.session.commit()
    wa.notify_request_received(req)
    log_action("pm.executed", entity_type="pm_schedule", entity_id=s.id, details=req.request_number)
    flash(f"تم توليد طلب {req.request_number}", "success")
    return redirect(url_for("pm.schedules_list"))


@pm_bp.route("/<int:sid>/toggle", methods=["POST"])
@admin_required
def toggle(sid):
    s = PMSchedule.query.get_or_404(sid)
    s.active = not s.active
    db.session.commit()
    flash("تم تغيير الحالة", "info")
    return redirect(url_for("pm.schedules_list"))
