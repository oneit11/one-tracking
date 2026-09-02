"""
Optional maintenance: prune old log rows to keep Postgres lean.

Files/images are NOT stored in Postgres (they live on Cloudinary), so the DB
should already be small. The only tables that grow unbounded over time are
activity logs. This script trims them, keeping recent history.

Deletes:
  - audit_logs      older than KEEP_DAYS (default 180)
  - whatsapp_logs   older than KEEP_DAYS
  - notifications    that are READ and older than 60 days

HOW TO RUN ON RAILWAY (only when you want to):
    python cleanup_db.py
Nothing else is touched — clients, requests, reports, accounts all stay.
"""
import os
from datetime import datetime, timedelta

from app import app
from models import db

KEEP_DAYS = int(os.getenv("LOG_KEEP_DAYS", "180"))


def run():
    cutoff = datetime.utcnow() - timedelta(days=KEEP_DAYS)
    notif_cutoff = datetime.utcnow() - timedelta(days=60)
    removed = {}
    with app.app_context():
        try:
            from models.extras import AuditLog, Notification
            removed["audit_logs"] = AuditLog.query.filter(
                AuditLog.created_at < cutoff).delete(synchronize_session=False)
        except Exception as e:
            print("audit_logs skip:", str(e)[:100]); removed["audit_logs"] = 0
        try:
            from models.wa_log import WhatsAppLog
            removed["whatsapp_logs"] = WhatsAppLog.query.filter(
                WhatsAppLog.sent_at < cutoff).delete(synchronize_session=False)
        except Exception as e:
            print("whatsapp_logs skip:", str(e)[:100]); removed["whatsapp_logs"] = 0
        try:
            from models.extras import Notification
            removed["notifications"] = Notification.query.filter(
                Notification.is_read.is_(True),
                Notification.created_at < notif_cutoff).delete(synchronize_session=False)
        except Exception as e:
            print("notifications skip:", str(e)[:100]); removed["notifications"] = 0
        db.session.commit()

        # Reclaim space on Postgres
        try:
            if db.engine.dialect.name == "postgresql":
                with db.engine.connect() as conn:
                    conn.execute(db.text("VACUUM"))
        except Exception as e:
            print("vacuum skip:", str(e)[:100])

    print("\n==================== CLEANUP DONE ====================")
    for k, v in removed.items():
        print(f"  {k}: removed {v} old rows")
    print(f"  (kept last {KEEP_DAYS} days of logs)")
    print("=====================================================")


if __name__ == "__main__":
    run()
