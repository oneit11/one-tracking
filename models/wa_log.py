from datetime import datetime
from models import db


class WhatsAppLog(db.Model):
    __tablename__ = "whatsapp_logs"

    id = db.Column(db.Integer, primary_key=True)
    to_number = db.Column(db.String(30), nullable=False, index=True)
    event_type = db.Column(db.String(50), default="")  # request_received, tech_assigned, report_ready, closed
    message_body = db.Column(db.Text, default="")
    related_entity_type = db.Column(db.String(30), default="")
    related_entity_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default="pending")  # pending, sent, failed
    provider_response = db.Column(db.Text, default="")
    error_message = db.Column(db.Text, default="")
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
