from datetime import datetime
from models import db


class Attachment(db.Model):
    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(30), nullable=False, index=True)  # client, device, request, report
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    file_url = db.Column(db.String(255), nullable=False)
    file_name = db.Column(db.String(200), default="")
    file_type = db.Column(db.String(30), default="")
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
