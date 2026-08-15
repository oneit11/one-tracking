from datetime import datetime
from models import db


class Setting(db.Model):
    """Key-value settings. Cached in-app on load."""
    __tablename__ = "settings"

    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text, default="")
    category = db.Column(db.String(30), default="general")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Categories: branding, company, whatsapp, sla, business_hours, other

    @classmethod
    def get(cls, key, default=""):
        s = cls.query.get(key)
        return s.value if s else default

    @classmethod
    def set(cls, key, value, category="general"):
        s = cls.query.get(key)
        if s:
            s.value = str(value) if value is not None else ""
            s.category = category
        else:
            s = cls(key=key, value=str(value) if value is not None else "", category=category)
            db.session.add(s)
        return s

    @classmethod
    def get_all_dict(cls):
        return {s.key: s.value for s in cls.query.all()}

    @classmethod
    def seed_defaults(cls, defaults_dict):
        """Seed defaults for keys that don't exist yet."""
        for key, (value, category) in defaults_dict.items():
            if not cls.query.get(key):
                db.session.add(cls(key=key, value=str(value), category=category))
        db.session.commit()


class MessageTemplate(db.Model):
    """Editable WhatsApp message templates with variable substitution."""
    __tablename__ = "message_templates"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, index=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    body = db.Column(db.Text, nullable=False)
    variables = db.Column(db.Text, default="")  # comma-separated variable names available
    active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Codes:
    # request_received_client / request_received_admin
    # tech_assigned_tech / tech_assigned_client
    # report_ready_client / report_ready_admin
    # request_closed_client / request_closed_admin
    # user_credentials  (login info to new users)
    # rating_request    (post-visit rating link)

    def render(self, **kwargs):
        """Substitute {var} with values."""
        text = self.body or ""
        for k, v in kwargs.items():
            text = text.replace("{" + k + "}", str(v) if v is not None else "")
        return text
