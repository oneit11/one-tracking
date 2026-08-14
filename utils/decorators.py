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


admin_required = role_required("admin")
tech_required = role_required("technician")
client_required = role_required("client")
staff_required = role_required("admin", "technician")
