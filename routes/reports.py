from datetime import datetime, timedelta
from io import BytesIO
from flask import Blueprint, render_template, request, send_file
from flask_login import login_required
from sqlalchemy import func, desc, and_
from models import db
from models.user import User
from models.client import Client, AMCContract
from models.device import Device
from models.request import MaintenanceRequest, VisitReport
from models.extras import Rating
from utils.decorators import admin_required
from services.pdf_service import PDFReport
from services.settings_service import get_setting
from services.audit import log_action

reports_bp = Blueprint("reports", __name__)


def _company_kwargs():
    return dict(
        company_name=get_setting("company_name", ""),
        company_phone=get_setting("company_phone", ""),
        company_email=get_setting("company_email", ""),
        primary_color=get_setting("primary_color", "#0b3d91"),
    )


def _date_range(default_days=30):
    to = request.args.get("to") or datetime.utcnow().strftime("%Y-%m-%d")
    default_from = (datetime.utcnow() - timedelta(days=default_days)).strftime("%Y-%m-%d")
    frm = request.args.get("from") or default_from
    return frm, to


@reports_bp.route("/")
@admin_required
def home():
    return render_template("admin/reports/home.html")


# ============ Client Statement ============
@reports_bp.route("/client/<int:cid>")
@admin_required
def client_statement(cid):
    client = Client.query.get_or_404(cid)
    return render_template("admin/reports/client_statement.html", client=client)


@reports_bp.route("/client/<int:cid>/pdf")
@admin_required
def client_statement_pdf(cid):
    client = Client.query.get_or_404(cid)
    pdf = PDFReport(
        title=f"كشف حساب عميل — {client.company_name}",
        subtitle=f"كود العميل: {client.code}",
        **_company_kwargs()
    )

    pdf.add_heading("بيانات العميل")
    pdf.add_key_value_table([
        ("الاسم", client.company_name),
        ("المسؤول", client.contact_person or "-"),
        ("التليفون", client.phone or "-"),
        ("الإيميل", client.email or "-"),
        ("العنوان", client.address or "-"),
    ])

    # Devices table
    pdf.add_heading(f"الأجهزة ({len(client.devices)})")
    rows = [[d.name, d.device_type or "-", d.brand or "-", d.location or "-"] for d in client.devices]
    if rows:
        pdf.add_table(["الاسم", "النوع", "الماركة", "الموقع"], rows)
    else:
        pdf.add_paragraph("لا يوجد أجهزة")

    # Requests
    reqs = MaintenanceRequest.query.filter_by(client_id=client.id).order_by(desc(MaintenanceRequest.created_at)).all()
    pdf.add_heading(f"سجل طلبات الصيانة ({len(reqs)})")
    rows = [[r.request_number, r.title[:40], r.status_label,
             r.created_at.strftime("%Y-%m-%d"), r.technician.name if r.technician else "-"] for r in reqs]
    if rows:
        pdf.add_table(["الرقم", "العنوان", "الحالة", "التاريخ", "الفني"], rows)
    else:
        pdf.add_paragraph("لا يوجد طلبات")

    # AMC contracts
    if client.amc_contracts:
        pdf.add_heading("عقود الصيانة (AMC)")
        rows = [[a.contract_number or "-",
                 a.start_date.strftime("%Y-%m-%d") if a.start_date else "-",
                 a.end_date.strftime("%Y-%m-%d") if a.end_date else "-",
                 f"{a.contract_value} ج.م",
                 a.visits_per_year] for a in client.amc_contracts]
        pdf.add_table(["رقم العقد", "من", "إلى", "القيمة", "زيارات/سنة"], rows)

    data = pdf.build()
    log_action("report.client_statement_pdf", entity_type="client", entity_id=cid)
    return send_file(BytesIO(data), mimetype="application/pdf",
                     as_attachment=True, download_name=f"Client-{client.code}.pdf")


# ============ Technician Performance ============
@reports_bp.route("/technician")
@admin_required
def tech_performance():
    frm, to = _date_range()
    frm_dt = datetime.strptime(frm, "%Y-%m-%d")
    to_dt = datetime.strptime(to, "%Y-%m-%d") + timedelta(days=1)

    techs = User.query.filter_by(role="technician").all()
    rows = []
    for t in techs:
        assigned = MaintenanceRequest.query.filter(
            MaintenanceRequest.technician_id == t.id,
            MaintenanceRequest.created_at.between(frm_dt, to_dt)
        ).count()
        closed = MaintenanceRequest.query.filter(
            MaintenanceRequest.technician_id == t.id,
            MaintenanceRequest.status == "closed",
            MaintenanceRequest.closed_at.between(frm_dt, to_dt)
        ).count()
        rows.append({"name": t.name, "assigned": assigned, "closed": closed,
                     "rate": f"{(closed/assigned*100):.0f}%" if assigned else "-"})
    return render_template("admin/reports/tech_performance.html", rows=rows, frm=frm, to=to)


@reports_bp.route("/technician/pdf")
@admin_required
def tech_performance_pdf():
    frm, to = _date_range()
    frm_dt = datetime.strptime(frm, "%Y-%m-%d")
    to_dt = datetime.strptime(to, "%Y-%m-%d") + timedelta(days=1)

    pdf = PDFReport(title="تقرير أداء الفنيين", subtitle=f"من {frm} إلى {to}", **_company_kwargs())
    techs = User.query.filter_by(role="technician").all()
    rows = []
    for t in techs:
        assigned = MaintenanceRequest.query.filter(
            MaintenanceRequest.technician_id == t.id,
            MaintenanceRequest.created_at.between(frm_dt, to_dt)).count()
        closed = MaintenanceRequest.query.filter(
            MaintenanceRequest.technician_id == t.id,
            MaintenanceRequest.status == "closed",
            MaintenanceRequest.closed_at.between(frm_dt, to_dt)).count()
        rows.append([t.name, assigned, closed,
                     f"{(closed/assigned*100):.0f}%" if assigned else "-"])
    pdf.add_table(["الفني", "المسندة", "المغلقة", "معدل الإنجاز"], rows)

    data = pdf.build()
    return send_file(BytesIO(data), mimetype="application/pdf",
                     as_attachment=True, download_name=f"TechPerformance-{frm}-{to}.pdf")


# ============ AMC Report ============
@reports_bp.route("/amc")
@admin_required
def amc_report():
    now = datetime.utcnow().date()
    active = AMCContract.query.filter(AMCContract.end_date >= now, AMCContract.active == True).all()  # noqa: E712
    expired = AMCContract.query.filter(AMCContract.end_date < now).all()
    expiring_soon = AMCContract.query.filter(
        AMCContract.end_date >= now,
        AMCContract.end_date <= now + timedelta(days=30)
    ).all()
    return render_template("admin/reports/amc.html",
                           active=active, expired=expired, expiring_soon=expiring_soon)


@reports_bp.route("/amc/pdf")
@admin_required
def amc_report_pdf():
    now = datetime.utcnow().date()
    pdf = PDFReport(title="تقرير عقود الصيانة (AMC)", **_company_kwargs())

    active = AMCContract.query.filter(AMCContract.end_date >= now, AMCContract.active == True).all()  # noqa: E712
    pdf.add_heading(f"عقود نشطة ({len(active)})")
    if active:
        rows = [[a.client.company_name, a.contract_number or "-",
                 a.end_date.strftime("%Y-%m-%d") if a.end_date else "-",
                 f"{a.contract_value} ج.م"] for a in active]
        pdf.add_table(["العميل", "رقم العقد", "تاريخ الانتهاء", "القيمة"], rows)

    expiring = AMCContract.query.filter(
        AMCContract.end_date >= now, AMCContract.end_date <= now + timedelta(days=30)
    ).all()
    pdf.add_heading(f"تنتهي خلال 30 يوم ({len(expiring)})")
    if expiring:
        rows = [[a.client.company_name, a.contract_number or "-",
                 a.end_date.strftime("%Y-%m-%d")] for a in expiring]
        pdf.add_table(["العميل", "رقم العقد", "تاريخ الانتهاء"], rows)

    expired = AMCContract.query.filter(AMCContract.end_date < now).all()
    pdf.add_heading(f"عقود منتهية ({len(expired)})")
    if expired:
        rows = [[a.client.company_name, a.contract_number or "-",
                 a.end_date.strftime("%Y-%m-%d") if a.end_date else "-"] for a in expired]
        pdf.add_table(["العميل", "رقم العقد", "انتهى في"], rows)

    data = pdf.build()
    return send_file(BytesIO(data), mimetype="application/pdf",
                     as_attachment=True, download_name="AMC-Report.pdf")


# ============ Requests Summary ============
@reports_bp.route("/requests")
@admin_required
def requests_summary():
    frm, to = _date_range()
    frm_dt = datetime.strptime(frm, "%Y-%m-%d")
    to_dt = datetime.strptime(to, "%Y-%m-%d") + timedelta(days=1)

    reqs = MaintenanceRequest.query.filter(
        MaintenanceRequest.created_at.between(frm_dt, to_dt)
    ).order_by(desc(MaintenanceRequest.created_at)).all()

    # Group by status
    status_counts = {}
    for r in reqs:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    return render_template("admin/reports/requests_summary.html",
                           reqs=reqs, status_counts=status_counts, frm=frm, to=to)


@reports_bp.route("/requests/pdf")
@admin_required
def requests_summary_pdf():
    frm, to = _date_range()
    frm_dt = datetime.strptime(frm, "%Y-%m-%d")
    to_dt = datetime.strptime(to, "%Y-%m-%d") + timedelta(days=1)

    pdf = PDFReport(title="ملخص طلبات الصيانة",
                    subtitle=f"من {frm} إلى {to}",
                    landscape_mode=True, **_company_kwargs())
    reqs = MaintenanceRequest.query.filter(
        MaintenanceRequest.created_at.between(frm_dt, to_dt)
    ).order_by(desc(MaintenanceRequest.created_at)).all()

    rows = [[r.request_number, r.client.company_name[:25],
             r.title[:35], r.priority_label, r.status_label,
             r.technician.name if r.technician else "-",
             r.created_at.strftime("%Y-%m-%d")] for r in reqs]
    pdf.add_table(
        ["الرقم", "العميل", "العنوان", "الأولوية", "الحالة", "الفني", "التاريخ"],
        rows
    )
    data = pdf.build()
    return send_file(BytesIO(data), mimetype="application/pdf",
                     as_attachment=True, download_name=f"Requests-{frm}-{to}.pdf")


# ============ Device history ============
@reports_bp.route("/device/<int:did>/pdf")
@admin_required
def device_history_pdf(did):
    device = Device.query.get_or_404(did)
    pdf = PDFReport(title=f"سجل صيانة الجهاز",
                    subtitle=f"{device.name} — {device.client.company_name}",
                    **_company_kwargs())

    pdf.add_heading("بيانات الجهاز")
    pdf.add_key_value_table([
        ("العميل", device.client.company_name),
        ("الاسم", device.name),
        ("النوع", device.device_type or "-"),
        ("الماركة/الموديل", f"{device.brand} {device.model}"),
        ("السيريال", device.serial_number or "-"),
        ("الموقع", device.location or "-"),
        ("تاريخ التركيب", device.installation_date.strftime("%Y-%m-%d") if device.installation_date else "-"),
    ])

    reqs = device.requests
    pdf.add_heading(f"سجل الصيانة ({len(reqs)})")
    if reqs:
        rows = [[r.request_number, r.title[:35], r.status_label,
                 r.created_at.strftime("%Y-%m-%d")] for r in reqs]
        pdf.add_table(["الرقم", "العنوان", "الحالة", "التاريخ"], rows)
    else:
        pdf.add_paragraph("لا يوجد سجل صيانة")

    data = pdf.build()
    return send_file(BytesIO(data), mimetype="application/pdf",
                     as_attachment=True, download_name=f"Device-{device.id}.pdf")


# ============ Request PDF ============
@reports_bp.route("/request/<int:rid>/pdf")
@admin_required
def request_pdf(rid):
    req = MaintenanceRequest.query.get_or_404(rid)
    pdf = PDFReport(title=f"طلب صيانة رقم {req.request_number}",
                    subtitle=req.title, **_company_kwargs())

    pdf.add_heading("تفاصيل الطلب")
    pdf.add_key_value_table([
        ("رقم الطلب", req.request_number),
        ("العميل", req.client.company_name),
        ("الجهاز", req.device.name if req.device else "-"),
        ("الأولوية", req.priority_label),
        ("الحالة", req.status_label),
        ("الفني", req.technician.name if req.technician else "-"),
        ("تاريخ الإنشاء", req.created_at.strftime("%Y-%m-%d %H:%M")),
        ("تاريخ الإغلاق", req.closed_at.strftime("%Y-%m-%d %H:%M") if req.closed_at else "-"),
    ])

    if req.description:
        pdf.add_heading("وصف المشكلة")
        pdf.add_paragraph(req.description)

    if req.visit_report:
        r = req.visit_report
        pdf.add_heading("تقرير الزيارة")
        pdf.add_key_value_table([
            ("الفني", r.technician.name),
            ("تاريخ الزيارة", r.visit_date.strftime("%Y-%m-%d %H:%M")),
            ("تم الحل", "نعم" if r.resolved else "لا"),
        ])
        if r.diagnosis:
            pdf.add_heading("التشخيص"); pdf.add_paragraph(r.diagnosis)
        if r.actions_taken:
            pdf.add_heading("الإجراءات"); pdf.add_paragraph(r.actions_taken)
        if r.spare_parts:
            pdf.add_heading("قطع الغيار"); pdf.add_paragraph(r.spare_parts)
        if r.recommendations:
            pdf.add_heading("التوصيات"); pdf.add_paragraph(r.recommendations)

    data = pdf.build()
    return send_file(BytesIO(data), mimetype="application/pdf",
                     as_attachment=True, download_name=f"Request-{req.request_number}.pdf")


# ============ Rating summary ============
@reports_bp.route("/ratings")
@admin_required
def ratings_report():
    ratings = Rating.query.filter(Rating.stars != None).order_by(desc(Rating.rated_at)).all()  # noqa: E711
    avg = 0
    if ratings:
        avg = sum(r.stars for r in ratings) / len(ratings)
    counts = {i: 0 for i in range(1, 6)}
    for r in ratings:
        counts[r.stars] = counts.get(r.stars, 0) + 1
    return render_template("admin/reports/ratings.html",
                           ratings=ratings, avg=avg, counts=counts)
