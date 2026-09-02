from datetime import datetime
from models import db


# ============ Permission catalog ============
# All permissions available in the system, grouped by module.
PERMISSION_CATALOG = {
    "clients": [
        ("clients.view", "عرض العملاء"),
        ("clients.create", "إضافة عميل"),
        ("clients.edit", "تعديل عميل"),
        ("clients.delete", "حذف عميل"),
        ("clients.export", "تصدير عملاء"),
    ],
    "devices": [
        ("devices.view", "عرض الأجهزة"),
        ("devices.create", "إضافة جهاز"),
        ("devices.edit", "تعديل جهاز"),
        ("devices.delete", "حذف جهاز"),
    ],
    "requests": [
        ("requests.view_all", "عرض كل طلبات الصيانة"),
        ("requests.view_own", "عرض الطلبات المعيّنة له فقط"),
        ("requests.create", "إنشاء طلب"),
        ("requests.assign", "تعيين فني"),
        ("requests.close", "إغلاق طلب"),
        ("requests.cancel", "إلغاء طلب"),
        ("requests.report", "رفع تقرير زيارة"),
        ("requests.comment", "إضافة تعليق داخلي"),
    ],
    "tickets": [
        ("tickets.view", "عرض التذاكر"),
        ("tickets.create", "إنشاء تذكرة"),
        ("tickets.resolve", "حل التذكرة"),
    ],
    "leads": [
        ("leads.view", "عرض الطلبات الواردة"),
        ("leads.manage", "تحويل / تعديل الطلبات الواردة"),
    ],
    "amc": [
        ("amc.view", "عرض عقود الصيانة"),
        ("amc.manage", "إدارة عقود AMC"),
    ],
    "qr": [
        ("qr.generate", "توليد باتش QR"),
        ("qr.print", "طباعة PDF"),
        ("qr.bind", "ربط QR بجهاز"),
    ],
    "inventory": [
        ("inventory.view", "عرض المخزون"),
        ("inventory.manage", "إدارة قطع الغيار"),
        ("inventory.movement", "حركة مخزنية"),
    ],
    "pm": [
        ("pm.view", "عرض الصيانة الوقائية"),
        ("pm.manage", "إدارة جداول PM"),
    ],
    "reports": [
        ("reports.view", "عرض التقارير"),
        ("reports.export_pdf", "تصدير PDF"),
        ("reports.export_excel", "تصدير Excel"),
    ],
    "users": [
        ("users.view", "عرض المستخدمين"),
        ("users.manage", "إدارة المستخدمين"),
        ("users.permissions", "إدارة صلاحيات"),
    ],
    "settings": [
        ("settings.view", "عرض الإعدادات"),
        ("settings.manage", "تعديل الإعدادات"),
        ("settings.whatsapp", "إدارة WhatsApp"),
        ("settings.branding", "تعديل الشكل والهوية"),
        ("settings.templates", "تعديل قوالب الرسايل"),
    ],
    "audit": [
        ("audit.view", "عرض سجل التتبع"),
    ],
    "system": [
        ("system.admin", "أدمن كامل (كل الصلاحيات)"),
    ],
}


def all_permission_codes():
    codes = []
    for group in PERMISSION_CATALOG.values():
        for code, _ in group:
            codes.append(code)
    return codes


# ============ Preset roles ============
PRESET_ROLES = {
    "admin": {
        "name": "أدمن",
        "description": "كل الصلاحيات",
        "permissions": ["system.admin"],  # meta-permission
    },
    "manager": {
        "name": "مدير",
        "description": "إدارة الطلبات والعملاء والتقارير",
        "permissions": [
            "clients.view", "clients.create", "clients.edit", "clients.export",
            "devices.view", "devices.create", "devices.edit",
            "requests.view_all", "requests.create", "requests.assign", "requests.close",
            "requests.comment",
            "tickets.view", "tickets.create", "tickets.resolve",
            "leads.view", "leads.manage",
            "amc.view", "amc.manage",
            "qr.generate", "qr.print", "qr.bind",
            "inventory.view", "inventory.movement",
            "reports.view", "reports.export_pdf", "reports.export_excel",
            "users.view",
        ],
    },
    "technician": {
        "name": "فني",
        "description": "المهام المعينة والتقارير",
        "permissions": [
            "requests.view_own", "requests.report", "requests.comment",
            "qr.bind",
            "inventory.view",
        ],
    },
    "receptionist": {
        "name": "استقبال",
        "description": "استقبال المكالمات وإنشاء طلبات",
        "permissions": [
            "clients.view", "clients.create", "clients.edit",
            "devices.view",
            "requests.view_all", "requests.create",
            "tickets.view", "tickets.create",
            "leads.view", "leads.manage",
        ],
    },
    "client": {
        "name": "عميل",
        "description": "بوابة العميل (Portal)",
        "permissions": [],  # handled separately in portal routes
    },
}


# ============ Models ============
class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, index=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, default="")
    is_system = db.Column(db.Boolean, default=False)
    permissions_csv = db.Column(db.Text, default="")  # comma-separated codes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def permissions_list(self):
        return [p.strip() for p in (self.permissions_csv or "").split(",") if p.strip()]

    @permissions_list.setter
    def permissions_list(self, codes):
        self.permissions_csv = ",".join(codes) if codes else ""


class UserPermissionOverride(db.Model):
    """Optional per-user permission overrides (granted or revoked on top of role)."""
    __tablename__ = "user_permission_overrides"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    permission_code = db.Column(db.String(80), nullable=False)
    granted = db.Column(db.Boolean, default=True)  # True=extra grant, False=explicit revoke

    __table_args__ = (
        db.UniqueConstraint("user_id", "permission_code", name="uq_user_perm"),
    )
