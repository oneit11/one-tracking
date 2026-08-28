from datetime import datetime
from models import db


class Client(db.Model):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, index=True)  # CL-000001
    company_name = db.Column(db.String(160), nullable=False)
    contact_person = db.Column(db.String(120), default="")
    phone = db.Column(db.String(30), default="", index=True)
    whatsapp = db.Column(db.String(30), default="")  # WA-enabled number (may differ)
    email = db.Column(db.String(120), default="")
    address = db.Column(db.Text, default="")
    city = db.Column(db.String(80), default="")
    logo_url = db.Column(db.String(255), default="")
    notes = db.Column(db.Text, default="")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ---- Account / credit control ----
    # credit_limit: max debt (positive number) the client is allowed to reach.
    # 0 (default) means "no limit" — the client is never blocked.
    credit_limit = db.Column(db.Numeric(12, 2), default=0)
    # When True, this client can never place a new request while they owe money
    # over the limit. When False (default) the limit is informational only.
    block_on_overdue = db.Column(db.Boolean, default=False)

    users = db.relationship("User", back_populates="client", foreign_keys="User.client_id")
    devices = db.relationship("Device", back_populates="client", cascade="all, delete-orphan")
    requests = db.relationship("MaintenanceRequest", back_populates="client")
    tickets = db.relationship("SupportTicket", back_populates="client")
    amc_contracts = db.relationship("AMCContract", back_populates="client", cascade="all, delete-orphan")
    account_entries = db.relationship(
        "AccountEntry", back_populates="client",
        cascade="all, delete-orphan", order_by="AccountEntry.created_at",
    )

    @property
    def notify_number(self):
        """WhatsApp number for notifications - falls back to phone."""
        return (self.whatsapp or self.phone or "").strip()

    # ---- Account helpers ----
    @property
    def total_charges(self):
        """Sum of everything billed to the client (invoices / visit costs)."""
        return float(sum(
            float(e.amount) for e in self.account_entries if e.entry_type == "charge"
        ))

    @property
    def total_payments(self):
        """Sum of everything the client has paid."""
        return float(sum(
            float(e.amount) for e in self.account_entries if e.entry_type == "payment"
        ))

    @property
    def balance(self):
        """Outstanding balance. Positive = client owes us (مدين).
        Negative = client is in credit (له رصيد / دفع مقدم)."""
        return round(self.total_charges - self.total_payments, 2)

    @property
    def is_overdue(self):
        """True when blocking is on AND the debt has passed the allowed limit."""
        if not self.block_on_overdue:
            return False
        limit = float(self.credit_limit or 0)
        # limit 0 = no ceiling
        if limit <= 0:
            return self.balance > 0
        return self.balance > limit

    @property
    def active_amc(self):
        today = datetime.utcnow().date()
        return next(
            (c for c in self.amc_contracts
             if c.start_date <= today <= c.end_date and c.active),
            None
        )

    def __repr__(self):
        return f"<Client {self.company_name}>"


class AMCContract(db.Model):
    __tablename__ = "amc_contracts"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    contract_number = db.Column(db.String(50), default="")
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    contract_value = db.Column(db.Numeric(12, 2), default=0)
    visits_per_year = db.Column(db.Integer, default=4)
    file_url = db.Column(db.String(255), default="")
    notes = db.Column(db.Text, default="")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship("Client", back_populates="amc_contracts")


class AccountEntry(db.Model):
    """One line on a client's financial statement (ledger).

    entry_type = "charge"  -> money the client owes us (invoice / visit cost)
    entry_type = "payment" -> money the client has paid us
    Balance = sum(charges) - sum(payments).
    """
    __tablename__ = "account_entries"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False, index=True)
    entry_type = db.Column(db.String(10), nullable=False, default="charge")  # charge | payment
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    description = db.Column(db.String(255), default="")
    # Optional link back to the maintenance request that generated a charge
    request_id = db.Column(db.Integer, db.ForeignKey("maintenance_requests.id"), nullable=True, index=True)
    # "visit" (auto from a closed request), "manual", "payment"
    source = db.Column(db.String(20), default="manual")
    method = db.Column(db.String(30), default="")  # payment method: cash/transfer/... (payments only)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    client = db.relationship("Client", back_populates="account_entries")
    request = db.relationship("MaintenanceRequest")

    TYPE_LABELS = {
        "charge": {"ar": "فاتورة / مستحق", "en": "Charge"},
        "payment": {"ar": "دفعة", "en": "Payment"},
    }

    @property
    def signed_amount(self):
        """+ for a charge, - for a payment (for running-balance display)."""
        amt = float(self.amount or 0)
        return amt if self.entry_type == "charge" else -amt
