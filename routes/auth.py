from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from models import db
from models.user import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("البريد الإلكتروني أو كلمة المرور غير صحيحة", "danger")
            return render_template("auth/login.html")
        if not user.active:
            flash("الحساب معطل، تواصل مع المسؤول", "warning")
            return render_template("auth/login.html")

        login_user(user, remember=remember)
        user.last_login = datetime.utcnow()
        db.session.commit()
        flash(f"مرحباً {user.name}", "success")
        return redirect(url_for("index"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("تم تسجيل الخروج", "info")
    return redirect(url_for("auth.login"))
