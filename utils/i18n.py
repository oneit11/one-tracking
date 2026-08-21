"""
Simple i18n system - dictionary-based translations.
Language stored in Flask session. Falls back to Arabic (default).
"""
from flask import session

# ============ Translations dictionary ============
# Add new keys here as needed. Missing keys fall back to the key itself.
TRANSLATIONS = {
    # Navigation
    "nav.dashboard": {"ar": "لوحة التحكم", "en": "Dashboard"},
    "nav.requests": {"ar": "الطلبات", "en": "Requests"},
    "nav.tickets": {"ar": "التذاكر", "en": "Tickets"},
    "nav.clients": {"ar": "العملاء", "en": "Clients"},
    "nav.devices": {"ar": "الأجهزة", "en": "Devices"},
    "nav.scan": {"ar": "📷 مسح", "en": "📷 Scan"},
    "nav.qr": {"ar": "QR", "en": "QR"},
    "nav.reports": {"ar": "تقارير", "en": "Reports"},
    "nav.inventory": {"ar": "مخزون", "en": "Inventory"},
    "nav.pm": {"ar": "الصيانة الوقائية", "en": "PM"},
    "nav.users": {"ar": "مستخدمين", "en": "Users"},
    "nav.whatsapp": {"ar": "واتس", "en": "WhatsApp"},
    "nav.settings": {"ar": "⚙️", "en": "⚙️"},
    "nav.logout": {"ar": "خروج", "en": "Logout"},
    "nav.notifications": {"ar": "التنبيهات", "en": "Notifications"},
    "nav.mytasks": {"ar": "مهامي", "en": "My Tasks"},
    "nav.portal_home": {"ar": "الرئيسية", "en": "Home"},
    "nav.my_devices": {"ar": "أجهزتي", "en": "My Devices"},
    "nav.my_requests": {"ar": "طلباتي", "en": "My Requests"},
    "nav.new_request": {"ar": "+ طلب صيانة", "en": "+ New Request"},
    "nav.install_app": {"ar": "📱 تثبيت", "en": "📱 Install"},
    "nav.mark_all_read": {"ar": "علّم الكل مقروء", "en": "Mark all as read"},
    "nav.view_all": {"ar": "عرض الكل", "en": "View all"},
    "nav.language": {"ar": "🌐 EN", "en": "🌐 عربي"},

    # Common buttons
    "btn.save": {"ar": "💾 حفظ", "en": "💾 Save"},
    "btn.cancel": {"ar": "إلغاء", "en": "Cancel"},
    "btn.delete": {"ar": "حذف", "en": "Delete"},
    "btn.edit": {"ar": "تعديل", "en": "Edit"},
    "btn.open": {"ar": "فتح", "en": "Open"},
    "btn.add": {"ar": "إضافة", "en": "Add"},
    "btn.back": {"ar": "← رجوع", "en": "← Back"},
    "btn.search": {"ar": "🔍 بحث", "en": "🔍 Search"},
    "btn.export_pdf": {"ar": "📄 تصدير PDF", "en": "📄 Export PDF"},
    "btn.send": {"ar": "إرسال", "en": "Send"},

    # Rating
    "rating.title": {"ar": "قيّم الخدمة", "en": "Rate our service"},
    "rating.subtitle": {"ar": "تقييمك يساعدنا نطور خدماتنا", "en": "Your feedback helps us improve"},
    "rating.company_section": {"ar": "تقييم الشركة والخدمة", "en": "Company & Service"},
    "rating.tech_section": {"ar": "تقييم الفني", "en": "Technician Rating"},
    "rating.comment_placeholder": {"ar": "شاركنا رأيك (اختياري)...", "en": "Share your thoughts (optional)..."},
    "rating.submit": {"ar": "إرسال التقييم", "en": "Submit Rating"},
    "rating.thanks_title": {"ar": "شكراً لك!", "en": "Thank you!"},
    "rating.thanks_body": {"ar": "تم تسجيل تقييمك بنجاح.", "en": "Your rating has been recorded successfully."},
    "rating.previous": {"ar": "تقييمك السابق:", "en": "Your previous rating:"},

    # Login
    "login.title": {"ar": "تسجيل الدخول", "en": "Sign In"},
    "login.email": {"ar": "البريد الإلكتروني", "en": "Email"},
    "login.password": {"ar": "كلمة المرور", "en": "Password"},
    "login.remember": {"ar": "تذكرني", "en": "Remember me"},
    "login.submit": {"ar": "دخول", "en": "Login"},

    # Settings
    "settings.language": {"ar": "لغة النظام", "en": "System Language"},
    "settings.arabic": {"ar": "العربية", "en": "Arabic"},
    "settings.english": {"ar": "الإنجليزية", "en": "English"},

    # Reports
    "reports.avg_rating": {"ar": "متوسط التقييم", "en": "Average Rating"},
    "reports.company_rating": {"ar": "تقييم الشركة", "en": "Company Rating"},
    "reports.tech_rating": {"ar": "تقييم الفني", "en": "Technician Rating"},
    "reports.ratings_title": {"ar": "تقييمات العملاء", "en": "Customer Ratings"},
    "reports.no_ratings": {"ar": "لا يوجد تقييمات بعد", "en": "No ratings yet"},
    "reports.home_title": {"ar": "📊 التقارير", "en": "📊 Reports"},
    "reports.requests_summary": {"ar": "📋 ملخص طلبات الصيانة", "en": "📋 Requests Summary"},
    "reports.requests_summary_desc": {"ar": "قائمة كل الطلبات في فترة زمنية محددة، مع تصدير PDF", "en": "All requests in a date range, with PDF export"},
    "reports.tech_perf": {"ar": "👨‍🔧 أداء الفنيين", "en": "👨‍🔧 Technician Performance"},
    "reports.tech_perf_desc": {"ar": "عدد المهام لكل فني ومعدل الإغلاق", "en": "Task count and closure rate per technician"},
    "reports.amc": {"ar": "📜 عقود AMC", "en": "📜 AMC Contracts"},
    "reports.amc_desc": {"ar": "العقود النشطة، المنتهية، والتي تنتهي قريباً", "en": "Active, expired, and expiring soon contracts"},
    "reports.ratings_desc": {"ar": "متوسط تقييم العملاء بعد الإغلاق", "en": "Customer ratings after request closure"},
    "reports.client_stmt": {"ar": "📄 كشف حساب عميل", "en": "📄 Client Statement"},
    "reports.client_stmt_desc": {"ar": "كشف الطلبات والفواتير لعميل معين", "en": "Requests and invoices statement for a client"},
    "reports.from": {"ar": "من", "en": "From"},
    "reports.to": {"ar": "إلى", "en": "To"},
    "reports.refresh": {"ar": "تحديث", "en": "Refresh"},
    "reports.date_range": {"ar": "من {frm} إلى {to}", "en": "From {frm} to {to}"},
    "reports.technician": {"ar": "الفني", "en": "Technician"},
    "reports.assigned": {"ar": "المسندة", "en": "Assigned"},
    "reports.closed": {"ar": "المغلقة", "en": "Closed"},
    "reports.completion_rate": {"ar": "معدل الإنجاز", "en": "Completion Rate"},

    # Rating - additional
    "rating.request_num": {"ar": "رقم الطلب", "en": "Request No."},
    "rating.client": {"ar": "العميل", "en": "Client"},
    "rating.technician_name": {"ar": "الفني", "en": "Technician"},
    "rating.service_title": {"ar": "الخدمة", "en": "Service"},
    "rating.print": {"ar": "🖨️ طباعة", "en": "🖨️ Print"},
    "rating.date": {"ar": "تاريخ التقييم", "en": "Rating Date"},

    # Status
    "status.new": {"ar": "جديد", "en": "New"},
    "status.assigned": {"ar": "تم التعيين", "en": "Assigned"},
    "status.in_progress": {"ar": "قيد التنفيذ", "en": "In Progress"},
    "status.report_ready": {"ar": "تقرير جاهز", "en": "Report Ready"},
    "status.closed": {"ar": "مغلق", "en": "Closed"},
    "status.cancelled": {"ar": "ملغي", "en": "Cancelled"},
}


AVAILABLE_LANGS = [("ar", "العربية"), ("en", "English")]


def get_current_lang():
    """Get current language from session (default: ar)."""
    return session.get("lang", "ar")


def set_lang(lang):
    """Set language in session."""
    if lang in [code for code, _ in AVAILABLE_LANGS]:
        session["lang"] = lang
        session.permanent = True
        return True
    return False


def t(key, **kwargs):
    """Translate a key. Falls back to key if not found."""
    lang = get_current_lang()
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key
    text = entry.get(lang) or entry.get("ar") or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def is_rtl():
    """Return True for RTL languages."""
    return get_current_lang() == "ar"
