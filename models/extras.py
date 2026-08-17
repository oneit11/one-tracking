from datetime import datetime
from models import db


class Notification(db.Model):
    """In-app notifications shown in the bell icon."""
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, default="")
    icon = db.Column(db.String(10), default="ð")
    link = db.Column(db.String(255), default="")
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class AuditLog(db.Model):
    """Tracks every important action."""
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    user_name = db.Column(db.String(120), default="")  # snapshot
    action = db.Column(db.String(80), nullable=False, index=True)
    entity_type = db.Column(db.String(50), default="", index=True)
    entity_id = db.Column(db.Integer, nullable=True, index=True)
    details = db.Column(db.Text, default="")
    ip = db.Column(db.String(50), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Comment(db.Model):
    """Internal comments on maintenance requests (staff-only)."""
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("maintenance_requests.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user_name = db.Column(db.String(120), default="")
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Rating(db.Model):
    """Post-visit rating from client. Separate scores for company and technician."""
    __tablename__ = "ratings"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("maintenance_requests.id"), nullable=False, unique=True)
    token = db.Column(db.String(40), unique=True, index=True)  # for anonymous access
    # Company/service rating
    stars = db.Column(db.Integer, nullable=True)  # 1-5
    comment = db.Column(db.Text, default="")
    # Technician rating
    tech_stars = db.Column(db.Integer, nullable=True)
    tech_comment = db.Column(db.Text, default="")
    rated_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    request = db.relationship("MaintenanceRequest", backref=db.backref("rating", uselist=False))


class SparePart(db.Model):
    """Spare parts inventory."""
    __tablename__ = "spare_parts"
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, index=True)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80), default="")
    unit = db.Column(db.String(30), default="ÙØ·Ø¹Ø©")
    quantity = db.Column(db.Numeric(12, 2), default=0)
    min_quantity = db.Column(db.Numeric(12, 2), default=0)
    unit_price = db.Column(db.Numeric(12, 2), default=0)
    location = db.Column(db.String(120), default="")
    notes = db.Column(db.Text, default="")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StockMovement(db.Model):
    """In/Out movements of spare parts."""
    __tablename__ = "stock_movements"
    id = db.Column(db.Integer, primary_key=True)
    part_id = db.Column(db.Integer, db.ForeignKey("spare_parts.id"), nullable=False, index=True)
    kind = db.Column(db.String(10), default="out")  # in, out, adjust
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), default=0)
    reference = db.Column(db.String(120), default="")  # e.g. MR26-0001
    notes = db.Column(db.Text, default="")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    part = db.relationship("SparePart", backref="movements")


class PMSchedule(db.Model):
    """Preventive Maintenance schedule (auto-generates requests)."""
    __tablename__ = "pm_schedules"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    device_id = db.Column(db.Integer, db.ForeignKey("devices.id"), nullable=True)
    interval_days = db.Column(db.Integer, default=90)  # every N days
    priority = db.Column(db.String(10), default="normal")
    description = db.Column(db.Text, default="")
    active = db.Column(db.Boolean, default=True)
    next_run = db.Column(db.Date, nullable=True, index=True)
    last_run = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship("Client")
    device = db.relationship("Device")
