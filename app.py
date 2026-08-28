import os
from flask import Flask, redirect, url_for, render_template, request as flask_request, jsonify, send_from_directory, abort
from flask_login import LoginManager, current_user
from config import Config
from models import db
from models.user import User


login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Cache-busting version for static assets: mtime of main.css. Changes on
    # every deploy that touches the CSS, so browsers always fetch the fresh file
    # instead of a stale cached copy (which breaks the layout after a redesign).
    try:
        css_path = os.path.join(app.root_path, "static", "css", "main.css")
        app.config["ASSET_VERSION"] = str(int(os.path.getmtime(css_path)))
    except Exception:
        app.config["ASSET_VERSION"] = "2"

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

    # Serve uploaded files from UPLOAD_FOLDER (works whether that's the default
    # static path or a mounted Railway volume). Shadows the default /static
    # handler for this subpath so existing /static/uploads/... URLs keep working.
    @app.route("/static/uploads/<path:filename>")
    def uploaded_file(filename):
        folder = app.config["UPLOAD_FOLDER"]
        full = os.path.join(folder, filename)
        if not os.path.isfile(full):
            abort(404)
        return send_from_directory(folder, filename)

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
        # Roll back any aborted transaction so the error page (and next request) is clean.
        try:
            db.session.rollback()
        except Exception:
            pass
        return render_template("errors/500.html"), 500

    @app.errorhandler(403)
    def forbidden(_):
        return render_template("errors/403.html"), 403

    # Template context — pull dynamic branding/company from DB
    @app.context_processor
    def inject_globals():
        from utils.i18n import t, get_current_lang, is_rtl, AVAILABLE_LANGS
        # Hard defaults — used if the DB is unreachable or the transaction is aborted,
        # so even the 500 error page always renders.
        ctx = {
            "APP_NAME": app.config["APP_NAME"],
            "APP_SHORT_NAME": "ONE Track",
            "LOGO_URL": "",
            "PRIMARY_COLOR": "#0b3d91",
            "ACCENT_COLOR": "#14b8a6",
            "THEME": "light",
            "COMPANY_NAME": app.config["COMPANY_NAME"],
            "COMPANY_PHONE": app.config["COMPANY_PHONE"],
            "COMPANY_PHONE_ALT": "",
            "COMPANY_EMAIL": app.config["COMPANY_EMAIL"],
            "COMPANY_ADDRESS": "",
            "t": t,
            "current_lang": get_current_lang(),
            "is_rtl": is_rtl(),
            "available_langs": AVAILABLE_LANGS,
            "nav_unread": 0,
            "ASSET_VERSION": app.config.get("ASSET_VERSION", "1"),
        }
        try:
            from services.settings_service import get_setting
            logo_url = get_setting("logo_url", "")
            # Drop a dead local logo path (file wiped by an ephemeral deploy)
            # so the page never requests a 404 image — falls back to the mark.
            if logo_url.startswith("/static/uploads/"):
                rel = logo_url[len("/static/uploads/"):]
                if not os.path.isfile(os.path.join(app.config["UPLOAD_FOLDER"], rel)):
                    logo_url = ""
            ctx.update({
                "APP_NAME": get_setting("app_name", app.config["APP_NAME"]),
                "APP_SHORT_NAME": get_setting("app_short_name", "ONE Track"),
                "LOGO_URL": logo_url,
                "PRIMARY_COLOR": get_setting("primary_color", "#0b3d91"),
                "ACCENT_COLOR": get_setting("accent_color", "#14b8a6"),
                "THEME": get_setting("theme", "light"),
                "COMPANY_NAME": get_setting("company_name", app.config["COMPANY_NAME"]),
                "COMPANY_PHONE": get_setting("company_phone", app.config["COMPANY_PHONE"]),
                "COMPANY_PHONE_ALT": get_setting("company_phone_alt", ""),
                "COMPANY_EMAIL": get_setting("company_email", app.config["COMPANY_EMAIL"]),
                "COMPANY_ADDRESS": get_setting("company_address", ""),
            })
        except Exception as e:
            db.session.rollback()
            app.logger.warning(f"inject_globals settings failed: {str(e)[:120]}")

        if current_user.is_authenticated:
            try:
                from services.notifications import unread_count
                ctx["nav_unread"] = unread_count(current_user.id)
            except Exception:
                db.session.rollback()
                ctx["nav_unread"] = 0
        return ctx

    # Startup: create tables, seed admin, seed settings/templates/roles
    with app.app_context():
        try:
            db.create_all()
            seed_default_admin(app)
            seed_defaults(app)
            _light_migrate(app)
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


def _light_migrate(app):
    """Automatic schema catch-up so deploys never leave the DB behind.

    1. create_all() adds any brand-new tables (e.g. followups).
    2. For every model table that already exists, compare the model's columns
       against the live DB and ALTER TABLE ADD COLUMN for anything missing.
       This auto-heals schema drift for present AND future columns.

    Runs on every startup. Each statement is isolated in its own transaction
    and rolled back on failure, so one problem can never poison later queries.
    Column-adding via ALTER TABLE is only attempted on PostgreSQL (prod);
    the SQLite dev DB is fully (re)built by create_all().
    """
    from sqlalchemy import inspect, text

    # 1) Create any missing tables outright.
    try:
        db.create_all()
    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"create_all warning: {str(e)[:150]}")

    # Backfill old visit costs onto client accounts (runs on any DB). Idempotent.
    _backfill_visit_charges(app)

    if db.engine.dialect.name != "postgresql":
        return

    # 2) Auto-add missing columns on existing tables.
    try:
        insp = inspect(db.engine)
        existing_tables = set(insp.get_table_names())
    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"inspect failed: {str(e)[:150]}")
        return

    for table in db.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all handles brand-new tables
        try:
            db_cols = {c["name"] for c in insp.get_columns(table.name)}
        except Exception as e:
            db.session.rollback()
            app.logger.warning(f"columns({table.name}) failed: {str(e)[:120]}")
            continue

        for col in table.columns:
            if col.name in db_cols:
                continue
            try:
                col_type = col.type.compile(dialect=db.engine.dialect)
            except Exception:
                col_type = "TEXT"
            ddl = f'ALTER TABLE {table.name} ADD COLUMN IF NOT EXISTS "{col.name}" {col_type}'
            try:
                db.session.execute(text(ddl))
                db.session.commit()
                app.logger.info(f"migrate: added {table.name}.{col.name}")
            except Exception as e:
                db.session.rollback()
                app.logger.warning(f"migrate skip {table.name}.{col.name}: {str(e)[:120]}")


def _backfill_visit_charges(app):
    """Create account charges for closed requests that have a visit_cost but no
    ledger entry yet. Safe to run on every startup (idempotent)."""
    try:
        from models.request import MaintenanceRequest
        from models.client import AccountEntry
    except Exception:
        return
    try:
        # Requests that carry a cost
        reqs = MaintenanceRequest.query.filter(
            MaintenanceRequest.visit_cost.isnot(None),
            MaintenanceRequest.visit_cost > 0,
        ).all()
    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"backfill query failed: {str(e)[:120]}")
        return

    created = 0
    for req in reqs:
        if not req.client_id:
            continue
        try:
            exists = AccountEntry.query.filter_by(
                request_id=req.id, source="visit", entry_type="charge"
            ).first()
            if exists:
                continue
            entry = AccountEntry(
                client_id=req.client_id,
                entry_type="charge",
                amount=float(req.visit_cost),
                description=f"تكلفة زيارة — طلب {req.request_number}",
                request_id=req.id,
                source="visit",
                created_at=req.closed_at or req.created_at,
            )
            db.session.add(entry)
            db.session.commit()
            created += 1
        except Exception as e:
            db.session.rollback()
            app.logger.warning(f"backfill skip req {req.id}: {str(e)[:120]}")
    if created:
        app.logger.info(f"backfill: created {created} visit charges")


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
