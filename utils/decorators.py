from functools import wraps
from flask import redirect, url_for, flash, abort
from flask_login import current_user


def role_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:
                flash("غير مصرح لك بالوصول لهذه الصفحة", "danger")
                abort(403)
            return fn(*args, **kwargs)
        return decorated
    return wrapper


def permission_required(*codes):
    """Requires any of the given permission codes."""
    def wrapper(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if not any(current_user.has_permission(c) for c in codes):
                flash("ليس لديك صلاحية للوصول لهذه الصفحة", "danger")
                abort(403)
            return fn(*args, **kwargs)
        return decorated
    return wrapper


def primary_admin_delete(fn):
    """Guard for destructive delete actions.

    Requires that the current user is the PRIMARY admin AND that they re-enter
    their own password in a `confirm_password` form field. Any other user (even
    another admin) is blocked. Wrap POST delete routes with this.
    """
    from functools import wraps as _wraps
    from flask import request as _request, flash as _flash, redirect as _redirect, url_for as _url_for
    from werkzeug.security import check_password_hash as _check

    @_wraps(fn)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return _redirect(_url_for("auth.login"))
        if not getattr(current_user, "is_primary_admin", False):
            _flash("هذا الإجراء متاح للأدمن الأساسي فقط", "danger")
            abort(403)
        pw = (_request.form.get("confirm_password") or "").strip()
        if not pw or not _check(current_user.password_hash, pw):
            _flash("كلمة السر غير صحيحة — لم يتم الحذف", "danger")
            # go back where they came from
            ref = _request.referrer or _url_for("admin.dashboard")
            return _redirect(ref)
        return fn(*args, **kwargs)
    return decorated


admin_required = role_required("admin")
tech_required = role_required("technician")
client_required = role_required("client")
staff_required = role_required("admin", "technician")
