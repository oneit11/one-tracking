from datetime import datetime
from flask_login import UserMixin
from models import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), default="")
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="client")  # admin, technician, client
    active = db.Column(db.Boolean, default=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relations
    client = db.relationship("Client", back_populates="users", foreign_keys=[client_id])
    assigned_requests = db.relationship(
        "MaintenanceRequest", back_populates="technician",
        foreign_keys="MaintenanceRequest.technician_id"
    )

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_technician(self):
        return self.role == "technician"

    @property
    def is_client(self):
        return self.role == "client"

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
