from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from sqlalchemy import desc, or_
from models import db
from models.request import MaintenanceRequest, VisitReport, SupportTicket, ProjectMember, ProjectVisit
from models.attachment import Attachment
from models.extras import Followup
from utils.decorators import tech_required
from utils.helpers import save_upload
from services import whatsapp as wa
from services.notifications import notify_admins

tech_bp = Blueprint("tech", __name__)


@tech_bp.route("/")
@tech_required
def dashboard():
    # Only OPEN requests assigned to this technician — closed ones are removed from view
    my_open = MaintenanceRequest.query.filter(
        MaintenanceRequest.technician_id == current_user.id,
        MaintenanceRequest.status.in_(["assigned", "in_progress", "report_ready"])
    ).order_by(desc(MaintenanceRequest.assigned_at)).all()

    # Upcoming follow-ups for this technician
    my_followups = Followup.query.filter(
        Followup.technician_id == current_user.id,
        Followup.status == "scheduled",
    ).order_by(Followup.scheduled_at.asc()).limit(20).all()

    # Open projects this technician is on (lead or member)
    my_project_ids = [m.ticket_id for m in ProjectMember.query.filter_by(user_id=current_user.id).all()]
    my_projects = []
    if my_project_ids:
        my_projects = SupportTicket.query.filter(
            SupportTicket.id.in_(my_project_ids),
            SupportTicket.status != "closed",
        ).order_by(desc(SupportTicket.created_at)).all()

    stats = {
        "open_count": len(my_open),
        "new": sum(1 for r in my_open if r.status == "assigned"),
        "in_progress": sum(1 for r in my_open if r.status == "in_progress"),
        "report_ready": sum(1 for r in my_open if r.status == "report_ready"),
        "followups": len(my_followups),
        "projects": len(my_projects),
    }

    return render_template("tech/dashboard.html", open_reqs=my_open,
                           followups=my_followups, stats=stats,
                           projects=my_projects, current_uid=current_user.id)


# ================= Projects =================
def _is_on_project(project):
    return any(u.id == current_user.id for u in project.team_users)


@tech_bp.route("/projects/<int:tid>")
@tech_required
def project_view(tid):
    project = SupportTicket.query.get_or_404(tid)
    if not _is_on_project(project):
        flash("هذا المشروع ليس ضمن فريقك", "warning")
        return redirect(url_for("tech.dashboard"))
    if project.status == "closed":
        flash("تم إغلاق هذا المشروع من قِبَل الإدارة", "info")
        return redirect(url_for("tech.dashboard"))
    is_lead = (project.assigned_to == current_user.id)
    return render_template("tech/project_view.html", project=project, is_lead=is_lead)


@tech_bp.route("/projects/<int:tid>/visit", methods=["POST"])
@tech_required
def project_visit_new(tid):
    project = SupportTicket.query.get_or_404(tid)
    # Only the team lead may log visits
    if project.assigned_to != current_user.id:
        flash("تسجيل الزيارات متاح لقائد الفريق فقط", "danger")
        return redirect(url_for("tech.project_view", tid=tid))

    visit = ProjectVisit(
        ticket_id=tid,
        technician_id=current_user.id,
        technician_name=current_user.name,
        visit_date=datetime.utcnow(),
        work_done=request.form.get("work_done", "").strip(),
        notes=request.form.get("notes", "").strip(),
    )
    db.session.add(visit)
    db.session.commit()

    # Multiple photos
    files = request.files.getlist("photos")
    saved = 0
    for f in files:
        if f and f.filename:
            url = save_upload(f, subfolder="reports", prefix="proj_")
            if url:
                db.session.add(Attachment(
                    entity_type="project_visit", entity_id=visit.id,
                    file_url=url, file_name=f.filename[:200], file_type="image",
                    uploaded_by=current_user.id,
                ))
                saved += 1
    db.session.commit()

    notify_admins(
        f"زيارة جديدة بمشروع {project.ticket_number}",
        f"{current_user.name} — {saved} صورة",
        "🏗️", url_for("admin.ticket_view", tid=tid),
    )
    flash(f"تم تسجيل الزيارة ({saved} صورة)", "success")
    return redirect(url_for("tech.project_view", tid=tid))


@tech_bp.route("/requests/<int:rid>")
@tech_required
def request_view(rid):
    req = MaintenanceRequest.query.get_or_404(rid)
    if req.technician_id != current_user.id:
        flash("هذا الطلب ليس معيناً عليك", "warning")
        return redirect(url_for("tech.dashboard"))
    # If the admin closed the request, remove it from the tech's view entirely
    if req.status == "closed":
        flash("تم إغلاق هذا الطلب من قِبَل الإدارة", "info")
        return redirect(url_for("tech.dashboard"))
    followups = Followup.query.filter_by(request_id=rid).order_by(Followup.scheduled_at.desc()).all()
    return render_template("tech/request_view.html", req=req, followups=followups)


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
    from services.notifications import notify_admins
    notify_admins(
        f"بدأ الفني العمل على {req.request_number}",
        f"{current_user.name} — {req.client.company_name}",
        "🔧", url_for("admin.request_view", rid=req.id),
    )
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

        # Optional: schedule a follow-up right from the report
        fu_date = request.form.get("followup_date", "").strip()
        fu_time = request.form.get("followup_time", "").strip() or "09:00"
        followup_at = request.form.get("followup_at", "").strip()  # legacy field
        fu_dt = None
        if fu_date:
            try:
                fu_dt = datetime.strptime(f"{fu_date} {fu_time}", "%Y-%m-%d %H:%M")
            except ValueError:
                fu_dt = None
        elif followup_at:
            try:
                fu_dt = datetime.strptime(followup_at, "%Y-%m-%dT%H:%M")
            except ValueError:
                fu_dt = None
        if fu_dt:
            fu = Followup(
                request_id=req.id,
                scheduled_at=fu_dt,
                technician_id=current_user.id,
                notes=request.form.get("followup_notes", "").strip(),
                created_by=current_user.id,
            )
            db.session.add(fu)

        db.session.commit()

        wa.notify_report_ready(req)
        from services.notifications import notify_admins
        notify_admins(
            f"تقرير فني جاهز {req.request_number}",
            f"{current_user.name} — {req.client.company_name}",
            "📋", url_for("admin.request_view", rid=req.id),
        )
        flash("تم رفع التقرير بنجاح", "success")
        return redirect(url_for("tech.request_view", rid=rid))

    return render_template("tech/report_form.html", req=req)
