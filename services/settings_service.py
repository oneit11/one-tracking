"""System settings - defaults and helper accessors."""
from models import db
from models.setting import Setting, MessageTemplate


# (key, default_value, category)
DEFAULT_SETTINGS = {
    # Branding
    "app_name": ("ONE Tracking", "branding"),
    "app_short_name": ("ONE Track", "branding"),
    "logo_url": ("", "branding"),
    "favicon_url": ("", "branding"),
    "primary_color": ("#0b3d91", "branding"),
    "accent_color": ("#14b8a6", "branding"),

    # Company
    "company_name": ("ONE For Integrated Solutions", "company"),
    "company_phone": ("01220733003", "company"),
    "company_phone_alt": ("01114994408", "company"),
    "company_email": ("info@one4in.com", "company"),
    "company_address": ("حدائق الأهرام - الجيزة", "company"),
    "company_website": ("https://one4in.com", "company"),
    # Bank details for visit-cost payment (shown to client on close)
    "bank_name": ("", "company"),
    "bank_account": ("", "company"),
    "currency": ("ج.م", "company"),

    # WhatsApp
    "wa_enabled": ("false", "whatsapp"),
    "wa_sidecar_url": ("", "whatsapp"),
    "wa_send_credentials_to_new_users": ("true", "whatsapp"),
    # Extra recipients: up to a few phone numbers that receive request/report
    # WhatsApp alerts just like the admin (comma or newline separated).
    "notify_extra_numbers": ("", "whatsapp"),

    # Business hours
    "biz_hours_start": ("09:00", "business_hours"),
    "biz_hours_end": ("18:00", "business_hours"),
    "biz_weekend": ("Friday,Saturday", "business_hours"),

    # SLA (hours) — response time by priority
    "sla_urgent_hours": ("2", "sla"),
    "sla_high_hours": ("8", "sla"),
    "sla_normal_hours": ("24", "sla"),
    "sla_low_hours": ("72", "sla"),

    # Rating
    # Email — send customer notifications by email alongside WhatsApp
    "smtp_enabled": ("false", "email"),
    # Provider: "brevo" (HTTP API — works on Railway) or "smtp" (often blocked on cloud hosts)
    "email_provider": ("brevo", "email"),
    "brevo_api_key": ("", "email"),      # Brevo (Sendinblue) HTTP API key
    "smtp_host": ("smtp.gmail.com", "email"),
    "smtp_port": ("587", "email"),
    "smtp_use_tls": ("true", "email"),
    "smtp_user": ("", "email"),          # e.g. info@one4in.com
    "smtp_password": ("", "email"),      # Google Workspace App Password
    "smtp_from_name": ("ONE For Integrated Solutions", "email"),
    "smtp_from_email": ("", "email"),    # defaults to smtp_user if empty

    "rating_enabled": ("true", "other"),
    "rating_link_message": ("قيّم الخدمة", "other"),
    # Social review links — shown to the customer after they rate, to invite
    # them to leave a public review on Facebook / Google.
    "facebook_page_url": ("", "social"),
    "google_review_url": ("", "social"),
    # Only invite a public review when the customer gave us this many stars+
    "social_review_min_stars": ("4", "social"),
}


DEFAULT_TEMPLATES = [
    {
        "code": "request_received_client",
        "name": "استلام الطلب (للعميل)",
        "description": "يُرسل للعميل عند استلام طلب صيانة",
        "variables": "client_name,request_number,title,company_name",
        "body": (
            "مرحباً {client_name} 👋\n\n"
            "تم استلام طلب الصيانة رقم: *{request_number}*\n"
            "العنوان: {title}\n"
            "سيتم التواصل معك قريباً لتعيين الفني.\n\n"
            "{company_name}"
        ),
    },
    {
        "code": "request_received_admin",
        "name": "استلام الطلب (للأدمن)",
        "description": "يُرسل للأدمن عند استلام طلب صيانة",
        "variables": "request_number,client_name,title,priority",
        "body": (
            "🔔 طلب صيانة جديد\n"
            "رقم: *{request_number}*\n"
            "العميل: {client_name}\n"
            "العنوان: {title}\n"
            "الأولوية: {priority}"
        ),
    },
    {
        "code": "tech_assigned_tech",
        "name": "تعيين مهمة (للفني)",
        "description": "يُرسل للفني عند تعيينه",
        "variables": "tech_name,request_number,client_name,client_phone,client_address,title,priority",
        "body": (
            "مرحباً {tech_name}\n\n"
            "تم تعيينك لمهمة صيانة جديدة:\n"
            "رقم الطلب: *{request_number}*\n"
            "العميل: {client_name}\n"
            "التليفون: {client_phone}\n"
            "العنوان: {client_address}\n"
            "المشكلة: {title}\n"
            "الأولوية: {priority}"
        ),
    },
    {
        "code": "tech_assigned_client",
        "name": "إشعار تعيين فني (للعميل)",
        "description": "يُرسل للعميل عند تعيين فني",
        "variables": "tech_name,request_number,company_name",
        "body": (
            "تم تعيين المهندس *{tech_name}* لطلب الصيانة رقم *{request_number}*.\n"
            "سيتواصل معك قريباً لتحديد موعد الزيارة.\n\n"
            "{company_name}"
        ),
    },
    {
        "code": "report_ready_client",
        "name": "تقرير جاهز (للعميل)",
        "description": "يُرسل للعميل عند رفع تقرير الفني",
        "variables": "request_number,portal_link,company_name",
        "body": (
            "تم رفع تقرير زيارة الصيانة لطلب *{request_number}*.\n"
            "يمكنك مراجعة التقرير من بوابتي:\n{portal_link}\n\n"
            "{company_name}"
        ),
    },
    {
        "code": "report_ready_admin",
        "name": "تقرير جاهز (للأدمن)",
        "description": "يُرسل للأدمن عند رفع تقرير الفني",
        "variables": "request_number,client_name,tech_name,resolved",
        "body": (
            "📋 تقرير زيارة جاهز\n"
            "طلب: *{request_number}*\n"
            "العميل: {client_name}\n"
            "الفني: {tech_name}\n"
            "الحالة: {resolved}"
        ),
    },
    {
        "code": "request_closed_client",
        "name": "إغلاق الطلب (للعميل)",
        "description": "يُرسل للعميل عند إغلاق الطلب",
        "variables": "request_number,rating_link,company_name",
        "body": (
            "تم إغلاق طلب الصيانة رقم *{request_number}* بنجاح.\n"
            "نرجو تقييم الخدمة من الرابط:\n{rating_link}\n\n"
            "شكراً لثقتكم بنا.\n\n"
            "{company_name}"
        ),
    },
    {
        "code": "request_closed_admin",
        "name": "إغلاق الطلب (للأدمن)",
        "description": "يُرسل للأدمن عند إغلاق الطلب",
        "variables": "request_number,client_name",
        "body": (
            "✅ تم إغلاق طلب\n"
            "رقم: *{request_number}*\n"
            "العميل: {client_name}"
        ),
    },
    {
        "code": "user_credentials",
        "name": "بيانات دخول مستخدم جديد",
        "description": "يُرسل للمستخدم عند إنشاء حسابه — بيانات الدخول",
        "variables": "user_name,email,password,app_url,company_name",
        "body": (
            "مرحباً {user_name} 👋\n\n"
            "تم إنشاء حسابك في نظام {company_name}\n\n"
            "بيانات الدخول:\n"
            "🔗 الرابط: {app_url}\n"
            "📧 البريد: {email}\n"
            "🔑 كلمة السر: {password}\n\n"
            "برجاء تغيير كلمة السر بعد أول دخول."
        ),
    },
]


def seed_settings_defaults():
    """Seed default settings and templates if empty."""
    Setting.seed_defaults(DEFAULT_SETTINGS)

    # Seed templates
    for tpl in DEFAULT_TEMPLATES:
        if not MessageTemplate.query.filter_by(code=tpl["code"]).first():
            db.session.add(MessageTemplate(**tpl))
    db.session.commit()


def get_setting(key, default=""):
    return Setting.get(key, default)


def get_settings_by_category(category):
    return {s.key: s.value for s in Setting.query.filter_by(category=category).all()}


def get_all_settings():
    return Setting.get_all_dict()
