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
    # For requests submitted via public QR scan (no login)
    source = db.Column(db.String(20), default="internal")  # internal, portal, qr
    contact_name = db.Column(db.String(120), default="")
    contact_phone = db.Column(db.String(30), default="")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    assigned_at = db.Column(db.DateTime, nullable=True)
    visit_at = db.Column(db.DateTime, nullable=True)  # scheduled visit date/time
    started_at = db.Column(db.DateTime, nullable=True)
    reported_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    # SLA
    sla_due_at = db.Column(db.DateTime, nullable=True, index=True)
    sla_breached = db.Column(db.Boolean, default=False)

    # Visit cost (set by admin at close)
    visit_cost = db.Column(db.Numeric(12, 2), nullable=True)

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
    admin_notes = db.Column(db.Text, default="")   # إضافات/مراجعة الإدارة قبل التصدير
    edited_by_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    request = db.relationship("MaintenanceRequest", back_populates="visit_report")
    technician = db.relationship("User")

    @property
    def attachments(self):
        from models.attachment import Attachment
        return Attachment.query.filter_by(entity_type="visit_report", entity_id=self.id)\
            .order_by(Attachment.uploaded_at).all()


class SupportTicket(db.Model):
    """Now used as a PROJECT: an open, multi-visit job for a team of technicians.
    No SLA / close deadline — has a start date and stays open until admin closes it."""
    __tablename__ = "support_tickets"

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, index=True)  # TK26-0001 (project code)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    priority = db.Column(db.String(10), default="normal")
    status = db.Column(db.String(20), default="open")  # open, in_progress, closed
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # team lead
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    # Project fields
    start_date = db.Column(db.Date, nullable=True)          # بداية العمل
    assigned_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    client = db.relationship("Client", back_populates="tickets")
    assignee = db.relationship("User", foreign_keys=[assigned_to])  # lead
    members = db.relationship("ProjectMember", back_populates="ticket",
                              cascade="all, delete-orphan")
    visits = db.relationship("ProjectVisit", back_populates="ticket",
                             cascade="all, delete-orphan", order_by="ProjectVisit.visit_date")

    STATUS_LABELS = {
        "open": "مفتوح",
        "in_progress": "قيد التنفيذ",
        "resolved": "تم الحل",
        "closed": "مغلق",
    }

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)

    @property
    def team_users(self):
        """All technicians on this project (lead + members), de-duplicated."""
        users = []
        seen = set()
        if self.assignee and self.assignee.id not in seen:
            users.append(self.assignee); seen.add(self.assignee.id)
        for m in self.members:
            if m.user and m.user.id not in seen:
                users.append(m.user); seen.add(m.user.id)
        return users


class ProjectMember(db.Model):
    """A technician assigned to a project (team member)."""
    __tablename__ = "project_members"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("support_tickets.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    is_lead = db.Column(db.Boolean, default=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    ticket = db.relationship("SupportTicket", back_populates="members")
    user = db.relationship("User")


class ProjectVisit(db.Model):
    """One site visit logged against a project (by the team lead). Has photos."""
    __tablename__ = "project_visits"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("support_tickets.id"), nullable=False, index=True)
    technician_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    technician_name = db.Column(db.String(120), default="")  # snapshot
    visit_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    work_done = db.Column(db.Text, default="")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ticket = db.relationship("SupportTicket", back_populates="visits")
    technician = db.relationship("User")

    @property
    def photos(self):
        from models.attachment import Attachment
        return Attachment.query.filter_by(entity_type="project_visit", entity_id=self.id)\
            .order_by(Attachment.uploaded_at).all()
