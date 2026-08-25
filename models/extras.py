from datetime import datetime
from models import db


class Notification(db.Model):
    """In-app notifications shown in the bell icon."""
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, default="")
    icon = db.Column(db.String(10), default="🔔")
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
    unit = db.Column(db.String(30), default="قطعة")
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


class Lead(db.Model):
    """A public service request from the marketing landing page (Facebook, etc.)."""
    __tablename__ = "leads"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False, index=True)
    customer_type = db.Column(db.String(40), default="")   # فرد/شركة/فندق/مستشفى...
    service_type = db.Column(db.String(60), default="")    # أمن/حريق/شبكات...
    description = db.Column(db.Text, default="")
    location = db.Column(db.String(200), default="")
    photo_url = db.Column(db.String(255), default="")
    source = db.Column(db.String(30), default="facebook")  # facebook, public, qr
    status = db.Column(db.String(20), default="new")       # new, contacted, converted, closed
    converted_request_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    STATUS_LABELS = {
        "new": "جديد",
        "contacted": "تم التواصل",
        "converted": "تحوّل لطلب",
        "closed": "مغلق",
    }

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)


class Survey(db.Model):
    """Site survey / معاينة: admin sends a technician to inspect a location,
    tech writes what's required + device items, admin uploads a price quote,
    and on customer approval it converts to an installation project."""
    __tablename__ = "surveys"
    id = db.Column(db.Integer, primary_key=True)
    survey_number = db.Column(db.String(20), unique=True, index=True)  # SV26-0001
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=True)
    contact_name = db.Column(db.String(120), default="")
    contact_phone = db.Column(db.String(30), default="")
    contact_email = db.Column(db.String(120), default="")
    location = db.Column(db.String(220), default="")
    description = db.Column(db.Text, default="")     # what the customer wants
    technician_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    visit_at = db.Column(db.DateTime, nullable=True)  # موعد المعاينة
    inspection_notes = db.Column(db.Text, default="")   # اللي شافه الفني والمطلوب
    inspected_at = db.Column(db.DateTime, nullable=True)
    quote_file_url = db.Column(db.String(255), default="")
    quote_amount = db.Column(db.Numeric(12, 2), nullable=True)
    quote_sent_at = db.Column(db.DateTime, nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    decision_note = db.Column(db.Text, default="")
    install_at = db.Column(db.DateTime, nullable=True)   # موعد التركيب
    converted_ticket_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default="new", index=True)
    # new, assigned, inspected, quoted, approved, converted, rejected
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    client = db.relationship("Client")
    technician = db.relationship("User", foreign_keys=[technician_id])
    items = db.relationship("SurveyItem", backref="survey",
                            cascade="all, delete-orphan", order_by="SurveyItem.id")

    STATUS_LABELS = {
        "new": "جديدة",
        "assigned": "مُسندة لفني",
        "inspected": "تمت المعاينة",
        "quoted": "تم إرسال العرض",
        "approved": "موافقة العميل",
        "converted": "تحوّلت لمشروع",
        "rejected": "مرفوضة",
    }

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)

    @property
    def customer_name(self):
        if self.client:
            return self.client.company_name
        return self.contact_name or "-"

    @property
    def customer_phone(self):
        if self.client and self.client.phone:
            return self.client.phone
        return self.contact_phone or ""

    @property
    def customer_email(self):
        if self.client and getattr(self.client, "email", ""):
            return self.client.email
        return (self.contact_email or "").strip()

    @property
    def attachments(self):
        from models.attachment import Attachment
        return Attachment.query.filter_by(entity_type="survey", entity_id=self.id)\
            .order_by(Attachment.uploaded_at).all()

    @property
    def items_total(self):
        total = 0
        for it in self.items:
            if it.unit_price:
                total += float(it.unit_price) * (it.quantity or 0)
        return total


class SurveyItem(db.Model):
    """A device/line-item on a survey — what will be installed."""
    __tablename__ = "survey_items"
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey("surveys.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)     # اسم الجهاز/البند
    spec = db.Column(db.String(200), default="")         # ماركة/موديل/مواصفات
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Numeric(12, 2), nullable=True)
    notes = db.Column(db.String(255), default="")
    added_by_role = db.Column(db.String(20), default="tech")  # tech / admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Followup(db.Model):
    """Follow-up appointment scheduled by admin/tech on a maintenance request that had a visit."""
    __tablename__ = "followups"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("maintenance_requests.id"), nullable=False, index=True)
    scheduled_at = db.Column(db.DateTime, nullable=False, index=True)
    technician_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    notes = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="scheduled")  # scheduled, done, cancelled
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    done_at = db.Column(db.DateTime, nullable=True)

    request = db.relationship("MaintenanceRequest", backref=db.backref("followups", cascade="all, delete-orphan"))
    technician = db.relationship("User", foreign_keys=[technician_id])

    STATUS_LABELS = {
        "scheduled": "مجدول",
        "done": "تم",
        "cancelled": "ملغي",
    }

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)


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
