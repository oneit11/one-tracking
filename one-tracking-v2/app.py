import os
from flask import Flask, redirect, url_for, render_template, request as flask_request, jsonify
from flask_login import LoginManager, current_user
from config import Config
from models import db
from models.user import User


login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure folders exist
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    for sub in ("clients", "devices", "reports", "qr", "amc", "branding", "avatars"):
        os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], sub), exist_ok=True)

    # Extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "يرجى تسجيل الدخول للوصول لهذه الصفحة"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints
    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.tech import tech_bp
    from routes.portal import portal_bp
    from routes.api import api_bp
    from routes.public import public_bp
    from routes.settings import settings_bp
    from routes.reports import reports_bp
    from routes.inventory import inventory_bp
    from routes.pm import pm_bp
    from routes.scanner import scanner_bp
    from routes.notifications import notifs_bp
    from routes.audit import audit_bp
    from routes.rating import rating_bp
    from routes.pwa import pwa_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(tech_bp, url_prefix="/tech")
    app.register_blueprint(portal_bp, url_prefix="/portal")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(public_bp)
    app.register_blueprint(settings_bp, url_prefix="/admin/settings")
    app.register_blueprint(reports_bp, url_prefix="/admin/reports")
    app.register_blueprint(inventory_bp, url_prefix="/admin/inventory")
    app.register_blueprint(pm_bp, url_prefix="/admin/pm")
    app.register_blueprint(scanner_bp)
    app.register_blueprint(notifs_bp)
    app.register_blueprint(audit_bp, url_prefix="/admin/audit")
    app.register_blueprint(rating_bp)
    app.register_blueprint(pwa_bp)

    # Root
    @app.route("/")
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        if current_user.role == "technician":
            return redirect(url_for("tech.dashboard"))
        return redirect(url_for("portal.dashboard"))

    # Errors
    @app.errorhandler(404)
    def not_found(_):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_):
        return render_template("errors/500.html"), 500

    @app.errorhandler(403)
    def forbidden(_):
        return render_template("errors/403.html"), 403

    # Template context — pull dynamic branding/company from DB
    @app.context_processor
    def inject_globals():
        from services.settings_service import get_setting
        from services.notifications import unread_count
        ctx = {
            "APP_NAME": get_setting("app_name", app.config["APP_NAME"]),
            "APP_SHORT_NAME": get_setting("app_short_name", "ONE Track"),
            "LOGO_URL": get_setting("logo_url", ""),
            "PRIMARY_COLOR": get_setting("primary_color", "#0b3d91"),
            "ACCENT_COLOR": get_setting("accent_color", "#14b8a6"),
            "COMPANY_NAME": get_setting("company_name", app.config["COMPANY_NAME"]),
            "COMPANY_PHONE": get_setting("company_phone", app.config["COMPANY_PHONE"]),
            "COMPANY_EMAIL": get_setting("company_email", app.config["COMPANY_EMAIL"]),
            "COMPANY_ADDRESS": get_setting("company_address", ""),
        }
        if current_user.is_authenticated:
            try:
                ctx["nav_unread"] = unread_count(current_user.id)
            except Exception:
                ctx["nav_unread"] = 0
        return ctx

    # Startup: create tables, seed admin, seed settings/templates/roles
    with app.app_context():
        try:
            db.create_all()
            seed_default_admin(app)
            seed_defaults(app)
        except Exception as e:
            app.logger.error(f"Startup DB error: {e}")

    return app


def seed_default_admin(app):
    from werkzeug.security import generate_password_hash
    if User.query.filter_by(role="admin").count() == 0:
        u = User(
            name=app.config["DEFAULT_ADMIN_NAME"],
            email=app.config["DEFAULT_ADMIN_EMAIL"],
            phone="",
            password_hash=generate_password_hash(app.config["DEFAULT_ADMIN_PASSWORD"]),
            role="admin",
            role_code="admin",
            active=True,
        )
        db.session.add(u)
        db.session.commit()


def seed_defaults(app):
    """Seed settings, templates, preset roles."""
    from services.settings_service import seed_settings_defaults
    from models.permission import Role, PRESET_ROLES

    seed_settings_defaults()

    for code, data in PRESET_ROLES.items():
        if not Role.query.filter_by(code=code).first():
            r = Role(
                code=code, name=data["name"], description=data["description"],
                is_system=True,
            )
            r.permissions_list = data["permissions"]
            db.session.add(r)
    db.session.commit()


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
