"""In-app notifications service."""
from models import db
from models.extras import Notification
from models.user import User


def notify_user(user_id, title, body="", icon="🔔", link=""):
    try:
        n = Notification(
            user_id=user_id,
            title=title,
            body=body,
            icon=icon,
            link=link,
        )
        db.session.add(n)
        db.session.commit()
    except Exception:
        db.session.rollback()


def notify_admins(title, body="", icon="🔔", link=""):
    admins = User.query.filter_by(role="admin", active=True).all()
    for a in admins:
        notify_user(a.id, title, body, icon, link)


def notify_role(role, title, body="", icon="🔔", link=""):
    users = User.query.filter_by(role=role, active=True).all()
    for u in users:
        notify_user(u.id, title, body, icon, link)


def unread_count(user_id):
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()


def recent_for_user(user_id, limit=10):
    return Notification.query.filter_by(user_id=user_id)\
        .order_by(Notification.created_at.desc()).limit(limit).all()


def mark_all_read(user_id):
    Notification.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})
    db.session.commit()
