import os
from flask import Flask, redirect, url_for, render_template
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
    for sub in ("clients", "devices", "reports", "qr", "amc"):
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

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(tech_bp, url_prefix="/tech")
    app.register_blueprint(portal_bp, url_prefix="/portal")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(public_bp)

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

    # Error handlers
    @app.errorhandler(404)
    def not_found(_):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_):
        return render_template("errors/500.html"), 500

    # Template globals
    @app.context_processor
    def inject_globals():
        return {
            "APP_NAME": app.config["APP_NAME"],
            "COMPANY_NAME": app.config["COMPANY_NAME"],
            "COMPANY_PHONE": app.config["COMPANY_PHONE"],
            "COMPANY_EMAIL": app.config["COMPANY_EMAIL"],
        }

    # Auto-create tables + seed admin
    with app.app_context():
        try:
            db.create_all()
            seed_default_admin(app)
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
            active=True,
        )
        db.session.add(u)
        db.session.commit()
        app.logger.info(f"Default admin created: {u.email}")


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
