"""
IoT devices — ESP32 sensor nodes that stream environmental readings
(temperature, humidity, smoke) from a client's server room.

Three tables:
    iot_devices  — the physical unit (paired to a client)
    iot_readings — time-series of telemetry (one row every ~30s)
    iot_alarms   — discrete events (smoke, out-of-range temp, offline)

The device authenticates on every request with two headers:
    X-Device-Id   the immutable id derived from its MAC (e.g. "SR-1A2B3C")
    X-Api-Key     a random 48-char key issued during provisioning

Provisioning flow:
    1. Admin creates a device row with a short claim_code (e.g. "742391").
    2. Admin ships the unit; end-user connects it to WiFi via captive portal
       and types the claim_code.
    3. First HTTPS POST /api/iot/provision hands the claim_code back with the
       device_id; server validates, generates api_key, returns it.
    4. Device stores api_key and starts sending telemetry.

Thresholds are per-device (server-room standards default to 18-27C / 30-60%).
"""
from datetime import datetime, timedelta
from models import db


class IoTDevice(db.Model):
    __tablename__ = "iot_devices"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(32), unique=True, index=True, nullable=True)
    # Random key issued on first successful provision. Empty until the device
    # calls /provision with a valid claim_code.
    api_key = db.Column(db.String(64), default="")
    # Short human-friendly code the admin gives the customer to type into the
    # captive portal. Unique while unclaimed; cleared after provisioning.
    claim_code = db.Column(db.String(16), index=True)

    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=True)
    name = db.Column(db.String(120), default="")           # "غرفة السيرفر الرئيسية"
    location = db.Column(db.String(200), default="")       # "الدور الأول - مكتب IT"
    notes = db.Column(db.Text, default="")

    # Thresholds — the client's server room is considered "healthy" when
    # temp is inside [temp_min, temp_max] and humidity inside [humid_min, humid_max].
    # Smoke_threshold triggers a temp-warning telemetry alarm; the digital DO
    # pin of the MQ sensor fires a smoke alarm immediately regardless.
    temp_min = db.Column(db.Float, default=18.0)
    temp_max = db.Column(db.Float, default=27.0)
    humid_min = db.Column(db.Float, default=30.0)
    humid_max = db.Column(db.Float, default=60.0)
    smoke_threshold = db.Column(db.Integer, default=2000)  # 0..4095 analog

    # Last-known state (denormalised for fast dashboards; the full history is
    # in iot_readings). Updated on every telemetry POST.
    last_seen = db.Column(db.DateTime)
    last_temp = db.Column(db.Float)
    last_humid = db.Column(db.Float)
    last_smoke_a = db.Column(db.Integer)
    last_smoke_d = db.Column(db.Boolean, default=False)
    last_rssi = db.Column(db.Integer)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    client = db.relationship("Client", backref=db.backref("iot_devices", lazy="dynamic"))

    # ---- Derived helpers ----
    @property
    def online(self):
        """A device is considered online if telemetry arrived within the last 90 seconds.
        This is critical for a safety-monitoring product: an offline device must be
        visually distinct so operators don't misread a stale value as current."""
        if not self.last_seen:
            return False
        return (datetime.utcnow() - self.last_seen) < timedelta(seconds=90)

    @property
    def temp_status(self):
        """green | yellow | red | gray — for a colour dot on the dashboard.
        Gray when offline or no reading — never show a colour based on stale data."""
        if not self.online or self.last_temp is None:
            return "gray"
        t = self.last_temp
        if t < self.temp_min - 2 or t > self.temp_max + 2:
            return "red"
        if t < self.temp_min or t > self.temp_max:
            return "yellow"
        return "green"

    @property
    def humid_status(self):
        if not self.online or self.last_humid is None:
            return "gray"
        h = self.last_humid
        if h < self.humid_min - 5 or h > self.humid_max + 5:
            return "red"
        if h < self.humid_min or h > self.humid_max:
            return "yellow"
        return "green"

    @property
    def smoke_status(self):
        if not self.online:
            return "gray"
        if self.last_smoke_d:
            return "red"
        if self.last_smoke_a is None:
            return "gray"
        if self.last_smoke_a > self.smoke_threshold:
            return "yellow"
        return "green"

    @property
    def overall_status(self):
        """Worst of temp/humid/smoke/offline. Drives the card colour."""
        if not self.online:
            return "gray"
        colours = [self.temp_status, self.humid_status, self.smoke_status]
        if "red" in colours:
            return "red"
        if "yellow" in colours:
            return "yellow"
        return "green"


class IoTReading(db.Model):
    __tablename__ = "iot_readings"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("iot_devices.id"), index=True, nullable=False)
    ts = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    temp = db.Column(db.Float)
    humidity = db.Column(db.Float)
    smoke_analog = db.Column(db.Integer)
    smoke_digital = db.Column(db.Boolean, default=False)

    device = db.relationship("IoTDevice", backref=db.backref("readings", lazy="dynamic"))


class IoTAlarm(db.Model):
    __tablename__ = "iot_alarms"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("iot_devices.id"), index=True, nullable=False)
    # smoke | temp_high | temp_low | humid_high | humid_low | offline
    alarm_type = db.Column(db.String(20), index=True)
    value = db.Column(db.Float)
    message = db.Column(db.String(300), default="")
    ts = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    notified = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime)

    device = db.relationship("IoTDevice", backref=db.backref("alarms", lazy="dynamic"))
