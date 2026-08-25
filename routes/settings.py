from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import db
from models.setting import Setting, MessageTemplate
from models.permission import Role, PRESET_ROLES, PERMISSION_CATALOG
from models.user import User
from utils.decorators import admin_required
from utils.helpers import save_upload
from services.settings_service import get_all_settings, get_settings_by_category, DEFAULT_TEMPLATES
from services.audit import log_action

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/")
@admin_required
def home():
    return render_template("admin/settings/home.html")


# ============ Branding ============
@settings_bp.route("/branding", methods=["GET", "POST"])
@admin_required
def branding():
    if request.method == "POST":
        for key in ["app_name", "app_short_name", "primary_color", "accent_color"]:
            val = request.form.get(key, "").strip()
            if val:
                Setting.set(key, val, "branding")

        if "logo" in request.files and request.files["logo"].filename:
            path = save_upload(request.files["logo"], subfolder="branding", prefix="logo_")
            if path:
                Setting.set("logo_url", path, "branding")

        if "favicon" in request.files and request.files["favicon"].filename:
            path = save_upload(request.files["favicon"], subfolder="branding", prefix="fav_")
            if path:
                Setting.set("favicon_url", path, "branding")

        db.session.commit()
        log_action("settings.branding_updated")
        flash("تم حفظ إعدادات الهوية", "success")
        return redirect(url_for("settings.branding"))

    s = get_settings_by_category("branding")
    return render_template("admin/settings/branding.html", s=s)


# ============ Company ============
@settings_bp.route("/company", methods=["GET", "POST"])
@admin_required
def company():
    if request.method == "POST":
        for key in ["company_name", "company_phone", "company_phone_alt",
                    "company_email", "company_address", "company_website",
                    "bank_name", "bank_account", "currency"]:
            val = request.form.get(key, "").strip()
            Setting.set(key, val, "company")
        # Extra WhatsApp recipients for request/report alerts (like admin)
        Setting.set("notify_extra_numbers",
                    request.form.get("notify_extra_numbers", "").strip(), "whatsapp")
        db.session.commit()
        log_action("settings.company_updated")
        flash("تم حفظ بيانات الشركة", "success")
        return redirect(url_for("settings.company"))

    s = get_settings_by_category("company")
    extra_numbers = get_all_settings().get("notify_extra_numbers", "")
    return render_template("admin/settings/company.html", s=s, extra_numbers=extra_numbers)


# ============ Business Hours + SLA ============
@settings_bp.route("/hours", methods=["GET", "POST"])
@admin_required
def hours():
    if request.method == "POST":
        for key in ["biz_hours_start", "biz_hours_end", "biz_weekend"]:
            val = request.form.get(key, "").strip()
            Setting.set(key, val, "business_hours")
        for key in ["sla_urgent_hours", "sla_high_hours", "sla_normal_hours", "sla_low_hours"]:
            val = request.form.get(key, "").strip()
            Setting.set(key, val, "sla")
        db.session.commit()
        log_action("settings.hours_updated")
        flash("تم حفظ ساعات العمل و SLA", "success")
        return redirect(url_for("settings.hours"))

    hours = get_settings_by_category("business_hours")
    sla = get_settings_by_category("sla")
    return render_template("admin/settings/hours.html", hours=hours, sla=sla)


@settings_bp.route("/email", methods=["GET", "POST"])
@admin_required
def email():
    if request.method == "POST":
        Setting.set("smtp_enabled", "true" if request.form.get("smtp_enabled") else "false", "email")
        Setting.set("smtp_use_tls", "true" if request.form.get("smtp_use_tls") else "false", "email")
        for key in ["smtp_host", "smtp_port", "smtp_user", "smtp_from_name", "smtp_from_email"]:
            Setting.set(key, request.form.get(key, "").strip(), "email")
        # Only overwrite the password if a new one was typed (so it isn't wiped on edit)
        pw = request.form.get("smtp_password", "")
        if pw.strip():
            Setting.set("smtp_password", pw.strip(), "email")
        db.session.commit()
        log_action("settings.email_updated")
        flash("تم حفظ إعدادات البريد الإلكتروني", "success")
        return redirect(url_for("settings.email"))

    s = get_settings_by_category("email")
    return render_template("admin/settings/email.html", s=s)


@settings_bp.route("/email/test", methods=["POST"])
@admin_required
def email_test():
    from services.email_service import send_test_email
    to = request.form.get("test_email", "").strip()
    if not to:
        flash("اكتب إيميل تجربة الأول", "warning")
        return redirect(url_for("settings.email"))
    ok, msg = send_test_email(to)
    flash(msg, "success" if ok else "danger")
    return redirect(url_for("settings.email"))


# ============ Message Templates ============
@settings_bp.route("/templates")
@admin_required
def templates_list():
    tpls = MessageTemplate.query.order_by(MessageTemplate.code).all()
    return render_template("admin/settings/templates_list.html", templates=tpls)


@settings_bp.route("/templates/<int:tid>", methods=["GET", "POST"])
@admin_required
def template_edit(tid):
    tpl = MessageTemplate.query.get_or_404(tid)
    if request.method == "POST":
        tpl.body = request.form.get("body", "").strip()
        tpl.active = bool(request.form.get("active"))
        db.session.commit()
        log_action("settings.template_updated", entity_type="template", entity_id=tpl.id, details=tpl.code)
        flash("تم حفظ القالب", "success")
        return redirect(url_for("settings.templates_list"))
    return render_template("admin/settings/template_form.html", tpl=tpl)


@settings_bp.route("/templates/reset/<int:tid>", methods=["POST"])
@admin_required
def template_reset(tid):
    tpl = MessageTemplate.query.get_or_404(tid)
    for d in DEFAULT_TEMPLATES:
        if d["code"] == tpl.code:
            tpl.body = d["body"]
            tpl.active = True
            db.session.commit()
            flash("تم استرجاع القالب الافتراضي", "info")
            break
    return redirect(url_for("settings.template_edit", tid=tid))


# ============ Roles & Permissions ============
@settings_bp.route("/roles")
@admin_required
def roles_list():
    roles = Role.query.order_by(Role.is_system.desc(), Role.name).all()
    return render_template("admin/settings/roles_list.html", roles=roles)


@settings_bp.route("/roles/new", methods=["GET", "POST"])
@admin_required
def role_new():
    if request.method == "POST":
        code = request.form.get("code", "").strip().lower()
        if not code or Role.query.filter_by(code=code).first():
            flash("كود الدور مستخدم أو فارغ", "danger")
            return redirect(url_for("settings.role_new"))
        r = Role(
            code=code,
            name=request.form.get("name", "").strip() or code,
            description=request.form.get("description", "").strip(),
            is_system=False,
        )
        r.permissions_list = request.form.getlist("permissions")
        db.session.add(r)
        db.session.commit()
        log_action("role.created", entity_type="role", entity_id=r.id, details=code)
        flash(f"تم إنشاء الدور {r.name}", "success")
        return redirect(url_for("settings.roles_list"))

    return render_template("admin/settings/role_form.html",
                           role=None, catalog=PERMISSION_CATALOG)


@settings_bp.route("/roles/<int:rid>", methods=["GET", "POST"])
@admin_required
def role_edit(rid):
    role = Role.query.get_or_404(rid)
    if request.method == "POST":
        if not role.is_system:  # can't change name/code of system roles
            role.name = request.form.get("name", role.name).strip()
            role.description = request.form.get("description", "").strip()
        role.permissions_list = request.form.getlist("permissions")
        db.session.commit()
        log_action("role.updated", entity_type="role", entity_id=role.id)
        flash("تم حفظ الدور", "success")
        return redirect(url_for("settings.roles_list"))
    return render_template("admin/settings/role_form.html",
                           role=role, catalog=PERMISSION_CATALOG)
