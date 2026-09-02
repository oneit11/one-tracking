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
    role = db.Column(db.String(20), nullable=False, default="client")  # legacy - kept for backward compat
    role_code = db.Column(db.String(30), default="")  # links to Role.code (custom roles)
    active = db.Column(db.Boolean, default=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=True)
    avatar_url = db.Column(db.String(255), default="")
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

    @property
    def role_display(self):
        """Human-readable role name from role_code (falls back to legacy role)."""
        code = self.role_code or self.role
        try:
            from models.permission import Role
            r = Role.query.filter_by(code=code).first()
            if r:
                return r.name
        except Exception:
            pass
        return {"admin": "أدمن", "technician": "فني", "client": "عميل",
                "manager": "مدير", "receptionist": "استقبال"}.get(code, code)

    def has_permission(self, code):
        """Check if user has a given permission code."""
        # Admin has all
        if self.role == "admin":
            return True

        # Client role handled separately (portal)
        if self.role == "client":
            return False

        # Overrides
        from models.permission import UserPermissionOverride
        overrides = {
            o.permission_code: o.granted
            for o in UserPermissionOverride.query.filter_by(user_id=self.id).all()
        }
        if code in overrides:
            return overrides[code]

        # Role permissions
        from models.permission import Role
        role = None
        if self.role_code:
            role = Role.query.filter_by(code=self.role_code).first()
        if not role and self.role:
            role = Role.query.filter_by(code=self.role).first()
        if not role:
            return False

        perms = role.permissions_list
        # Meta permission grants all
        if "system.admin" in perms:
            return True
        return code in perms

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
