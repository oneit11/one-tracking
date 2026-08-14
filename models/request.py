from datetime import datetime
from models import db


class MaintenanceRequest(db.Model):
    __tablename__ = "maintenance_requests"

    id = db.Column(db.Integer, primary_key=True)
    request_number = db.Column(db.String(20), unique=True, index=True)  # MR26-0001
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    device_id = db.Column(db.Integer, db.ForeignKey("devices.id"), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    priority = db.Column(db.String(10), default="normal")  # low, normal, high, urgent
    status = db.Column(db.String(20), default="new")
    # Statuses: new, assigned, in_progress, report_ready, closed, cancelled

    submitted_photo_url = db.Column(db.String(255), default="")
    technician_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    assigned_at = db.Column(db.DateTime, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    reported_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    client = db.relationship("Client", back_populates="requests")
    device = db.relationship("Device", back_populates="requests")
    technician = db.relationship("User", back_populates="assigned_requests", foreign_keys=[technician_id])
    creator = db.relationship("User", foreign_keys=[created_by])
    visit_report = db.relationship("VisitReport", back_populates="request", uselist=False, cascade="all, delete-orphan")

    STATUS_LABELS = {
        "new": "جديد",
        "assigned": "تم التعيين",
        "in_progress": "قيد التنفيذ",
        "report_ready": "التقرير جاهز",
        "closed": "مغلق",
        "cancelled": "ملغي",
    }

    PRIORITY_LABELS = {
        "low": "منخفض",
        "normal": "عادي",
        "high": "عالي",
        "urgent": "عاجل",
    }

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)

    @property
    def priority_label(self):
        return self.PRIORITY_LABELS.get(self.priority, self.priority)


class VisitReport(db.Model):
    __tablename__ = "visit_reports"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("maintenance_requests.id"), nullable=False, unique=True)
    technician_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    visit_date = db.Column(db.DateTime, default=datetime.utcnow)
    diagnosis = db.Column(db.Text, default="")
    actions_taken = db.Column(db.Text, default="")
    spare_parts = db.Column(db.Text, default="")
    recommendations = db.Column(db.Text, default="")
    resolved = db.Column(db.Boolean, default=True)
    photo_url = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    request = db.relationship("MaintenanceRequest", back_populates="visit_report")
    technician = db.relationship("User")


class SupportTicket(db.Model):
    __tablename__ = "support_tickets"

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, index=True)  # TK26-0001
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    priority = db.Column(db.String(10), default="normal")
    status = db.Column(db.String(20), default="open")  # open, in_progress, resolved, closed
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    client = db.relationship("Client", back_populates="tickets")
    assignee = db.relationship("User", foreign_keys=[assigned_to])

    STATUS_LABELS = {
        "open": "مفتوح",
        "in_progress": "قيد المعالجة",
        "resolved": "تم الحل",
        "closed": "مغلق",
    }

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)
