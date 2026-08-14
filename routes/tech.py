from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import desc, or_
from models import db
from models.request import MaintenanceRequest, VisitReport
from utils.decorators import tech_required
from utils.helpers import save_upload
from services import whatsapp as wa

tech_bp = Blueprint("tech", __name__)


@tech_bp.route("/")
@tech_required
def dashboard():
    my_open = MaintenanceRequest.query.filter(
        MaintenanceRequest.technician_id == current_user.id,
        MaintenanceRequest.status.in_(["assigned", "in_progress", "report_ready"])
    ).order_by(desc(MaintenanceRequest.assigned_at)).all()

    my_closed = MaintenanceRequest.query.filter(
        MaintenanceRequest.technician_id == current_user.id,
        MaintenanceRequest.status == "closed"
    ).order_by(desc(MaintenanceRequest.closed_at)).limit(10).all()

    return render_template("tech/dashboard.html", open_reqs=my_open, closed_reqs=my_closed)


@tech_bp.route("/requests/<int:rid>")
@tech_required
def request_view(rid):
    req = MaintenanceRequest.query.get_or_404(rid)
    if req.technician_id != current_user.id:
        flash("هذا الطلب ليس معيناً عليك", "warning")
        return redirect(url_for("tech.dashboard"))
    return render_template("tech/request_view.html", req=req)


@tech_bp.route("/requests/<int:rid>/start", methods=["POST"])
@tech_required
def request_start(rid):
    req = MaintenanceRequest.query.get_or_404(rid)
    if req.technician_id != current_user.id:
        flash("غير مصرح", "danger")
        return redirect(url_for("tech.dashboard"))
    req.status = "in_progress"
    req.started_at = datetime.utcnow()
    db.session.commit()
    flash("بدأ العمل على الطلب", "info")
    return redirect(url_for("tech.request_view", rid=rid))


@tech_bp.route("/requests/<int:rid>/report", methods=["GET", "POST"])
@tech_required
def submit_report(rid):
    req = MaintenanceRequest.query.get_or_404(rid)
    if req.technician_id != current_user.id:
        flash("غير مصرح", "danger")
        return redirect(url_for("tech.dashboard"))

    if request.method == "POST":
        # If report exists, update it. Otherwise create new.
        report = req.visit_report or VisitReport(request_id=req.id, technician_id=current_user.id)
        report.diagnosis = request.form.get("diagnosis", "").strip()
        report.actions_taken = request.form.get("actions_taken", "").strip()
        report.spare_parts = request.form.get("spare_parts", "").strip()
        report.recommendations = request.form.get("recommendations", "").strip()
        report.resolved = bool(request.form.get("resolved"))
        report.visit_date = datetime.utcnow()

        if "photo" in request.files and request.files["photo"].filename:
            p = save_upload(request.files["photo"], subfolder="reports", prefix="rep_")
            if p:
                report.photo_url = p

        if not req.visit_report:
            db.session.add(report)

        req.status = "report_ready"
        req.reported_at = datetime.utcnow()
        db.session.commit()

        wa.notify_report_ready(req)
        flash("تم رفع التقرير بنجاح", "success")
        return redirect(url_for("tech.request_view", rid=rid))

    return render_template("tech/report_form.html", req=req)
