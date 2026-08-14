from datetime import datetime
from models import db


class Device(db.Model):
    __tablename__ = "devices"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    device_type = db.Column(db.String(60), default="")  # camera, dvr, access, fire, network...
    brand = db.Column(db.String(80), default="")
    model = db.Column(db.String(80), default="")
    serial_number = db.Column(db.String(80), default="", index=True)
    location = db.Column(db.String(160), default="")  # in-facility location
    installation_date = db.Column(db.Date, nullable=True)
    warranty_end = db.Column(db.Date, nullable=True)
    photo_url = db.Column(db.String(255), default="")
    notes = db.Column(db.Text, default="")
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship("Client", back_populates="devices")
    qr_code = db.relationship("QRCode", back_populates="device", uselist=False)
    requests = db.relationship("MaintenanceRequest", back_populates="device")

    DEVICE_TYPES = [
        ("camera", "كاميرا مراقبة"),
        ("dvr", "DVR / NVR"),
        ("access", "Access Control"),
        ("fire", "Fire Alarm"),
        ("network", "شبكة / سويتش"),
        ("intercom", "انتركم"),
        ("audio", "صوتيات"),
        ("other", "أخرى"),
    ]


class QRBatch(db.Model):
    __tablename__ = "qr_batches"

    id = db.Column(db.Integer, primary_key=True)
    batch_code = db.Column(db.String(30), unique=True, index=True)  # BATCH-2026-0001
    count = db.Column(db.Integer, nullable=False)
    size = db.Column(db.String(10), default="medium")  # small, medium, large
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, default="")

    codes = db.relationship("QRCode", back_populates="batch", cascade="all, delete-orphan")

    @property
    def used_count(self):
        return sum(1 for c in self.codes if c.device_id)

    @property
    def unused_count(self):
        return self.count - self.used_count


class QRCode(db.Model):
    __tablename__ = "qr_codes"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, index=True, nullable=False)  # ONE-QR-2026-000001
    batch_id = db.Column(db.Integer, db.ForeignKey("qr_batches.id"), nullable=False)
    device_id = db.Column(db.Integer, db.ForeignKey("devices.id"), nullable=True, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    bound_at = db.Column(db.DateTime, nullable=True)

    batch = db.relationship("QRBatch", back_populates="codes")
    device = db.relationship("Device", back_populates="qr_code")

    @property
    def is_bound(self):
        return self.device_id is not None
