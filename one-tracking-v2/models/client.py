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

    users = db.relationship("User", back_populates="client", foreign_keys="User.client_id")
    devices = db.relationship("Device", back_populates="client", cascade="all, delete-orphan")
    requests = db.relationship("MaintenanceRequest", back_populates="client")
    tickets = db.relationship("SupportTicket", back_populates="client")
    amc_contracts = db.relationship("AMCContract", back_populates="client", cascade="all, delete-orphan")

    @property
    def notify_number(self):
        """WhatsApp number for notifications - falls back to phone."""
        return (self.whatsapp or self.phone or "").strip()

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
