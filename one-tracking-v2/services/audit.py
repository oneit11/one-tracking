"""Audit logging service."""
from flask import request as flask_request
from flask_login import current_user
from models import db
from models.extras import AuditLog


def log_action(action, entity_type="", entity_id=None, details=""):
    """Log an audit event. Safe to call from any route."""
    try:
        user_id = None
        user_name = ""
        if current_user and current_user.is_authenticated:
            user_id = current_user.id
            user_name = current_user.name

        ip = ""
        try:
            ip = (flask_request.headers.get("X-Forwarded-For") or flask_request.remote_addr or "")[:50]
        except Exception:
            pass

        entry = AuditLog(
            user_id=user_id,
            user_name=user_name,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=str(details)[:500] if details else "",
            ip=ip,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
