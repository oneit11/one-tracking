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
    "nav.my_account": {"ar": "💰 حسابي", "en": "💰 My Account"},
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
    "btn.print": {"ar": "🖨️ طباعة", "en": "🖨️ Print"},

    # Account / statement
    "account.my_account": {"ar": "حسابي", "en": "My Account"},
    "account.statement": {"ar": "كشف الحساب", "en": "Account Statement"},
    "account.total_charges": {"ar": "إجمالي المستحقات", "en": "Total Charges"},
    "account.total_payments": {"ar": "إجمالي المدفوعات", "en": "Total Payments"},
    "account.balance": {"ar": "الرصيد", "en": "Balance"},
    "account.you_owe": {"ar": "المستحق عليك", "en": "You Owe"},
    "account.in_credit": {"ar": "رصيد لك", "en": "In Credit"},
    "account.date": {"ar": "التاريخ", "en": "Date"},
    "account.description": {"ar": "البيان", "en": "Description"},
    "account.charge": {"ar": "مستحق", "en": "Charge"},
    "account.payment": {"ar": "مدفوع", "en": "Payment"},
    "account.running_balance": {"ar": "الرصيد", "en": "Balance"},
    "account.no_entries": {"ar": "لا يوجد حركات على الحساب بعد", "en": "No account activity yet"},
    "account.pay_via": {"ar": "بيانات السداد", "en": "Payment Details"},
    "account.bank": {"ar": "البنك", "en": "Bank"},
    "account.account_no": {"ar": "رقم الحساب", "en": "Account No."},
    "account.blocked_title": {"ar": "الطلب متوقف مؤقتاً", "en": "Request Blocked"},
    "account.credit_limit": {"ar": "حد الدين المسموح", "en": "Credit Limit"},
    "account.view_statement": {"ar": "عرض كشف الحساب", "en": "View Statement"},
    "account.please_pay": {"ar": "برجاء سداد المبلغ المتأخر لإكمال الطلب",
                            "en": "Please settle your overdue balance to place a new request"},

    # Rating
    "rating.title": {"ar": "قيّم الخدمة", "en": "Rate our service"},
    "rating.share_prompt": {"ar": "يسعدنا لو شاركت رأيك مع الآخرين",
                             "en": "We'd love it if you shared your experience"},
    "rating.review_google": {"ar": "قيّمنا على Google", "en": "Review us on Google"},
    "rating.review_facebook": {"ar": "قيّمنا على فيسبوك", "en": "Review us on Facebook"},
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

    # Portal
    "portal.welcome": {"ar": "مرحباً، {name}", "en": "Welcome, {name}"},
    "portal.subtitle": {"ar": "بوابة إدارة الصيانة والدعم", "en": "Maintenance & Support Portal"},
    "portal.my_devices": {"ar": "أجهزتي", "en": "My Devices"},
    "portal.open_requests": {"ar": "طلبات مفتوحة", "en": "Open Requests"},
    "portal.closed_requests": {"ar": "طلبات مغلقة", "en": "Closed Requests"},
    "portal.open_projects": {"ar": "مشاريع مفتوحة", "en": "Open Projects"},
    "portal.my_account_card": {"ar": "حسابي", "en": "My Account"},
    "portal.amc_active": {"ar": "عقد AMC ساري", "en": "Active AMC"},
    "portal.until": {"ar": "حتى {date}", "en": "Until {date}"},
    "portal.overdue_warning": {"ar": "برجاء سداد المبلغ المتأخر ({amount}) لإكمال طلباتك الجديدة.",
                                "en": "Please settle your overdue balance ({amount}) to place new requests."},
    "portal.recent_open": {"ar": "أحدث طلباتي المفتوحة", "en": "My Recent Open Requests"},
    "portal.view_all": {"ar": "عرض الكل ←", "en": "View all →"},
    "portal.no_open": {"ar": "لا يوجد طلبات مفتوحة", "en": "No open requests"},
    "portal.first_request": {"ar": "+ أول طلب صيانة", "en": "+ First maintenance request"},
    "portal.qa_new": {"ar": "طلب جديد", "en": "New Request"},
    "portal.qa_requests": {"ar": "طلباتي", "en": "My Requests"},
    "portal.qa_devices": {"ar": "أجهزتي", "en": "My Devices"},
    "portal.owed_by_you": {"ar": "مستحق عليك", "en": "You owe"},
    "portal.credit_you": {"ar": "رصيد لك", "en": "In credit"},

    # Requests (portal)
    "req.new_title": {"ar": "طلب صيانة جديد", "en": "New Maintenance Request"},
    "req.device_optional": {"ar": "الجهاز (اختياري)", "en": "Device (optional)"},
    "req.general": {"ar": "-- طلب عام --", "en": "-- General --"},
    "req.priority": {"ar": "الأولوية", "en": "Priority"},
    "req.title_label": {"ar": "العنوان", "en": "Title"},
    "req.title_ph": {"ar": "مثال: الكاميرا في المدخل لا تعمل", "en": "e.g. The entrance camera is not working"},
    "req.desc_label": {"ar": "وصف المشكلة", "en": "Problem description"},
    "req.desc_ph": {"ar": "اذكر أي تفاصيل تساعد الفني...", "en": "Any details that help the technician..."},
    "req.photo_label": {"ar": "صورة المشكلة", "en": "Problem photo"},
    "req.photo_hint": {"ar": "تساعد الفني في تشخيص المشكلة قبل الزيارة", "en": "Helps the technician diagnose before the visit"},
    "req.submit": {"ar": "📤 إرسال الطلب", "en": "📤 Submit Request"},
    "req.list_title": {"ar": "طلبات الصيانة", "en": "Maintenance Requests"},
    "req.new_btn": {"ar": "+ طلب جديد", "en": "+ New Request"},
    "req.tab_open": {"ar": "المفتوحة", "en": "Open"},
    "req.tab_closed": {"ar": "المغلقة", "en": "Closed"},
    "req.tab_all": {"ar": "الكل", "en": "All"},
    "req.col_number": {"ar": "الرقم", "en": "No."},
    "req.col_subject": {"ar": "الموضوع", "en": "Subject"},
    "req.col_device": {"ar": "الجهاز", "en": "Device"},
    "req.col_status": {"ar": "الحالة", "en": "Status"},
    "req.col_date": {"ar": "التاريخ", "en": "Date"},
    "priority.low": {"ar": "منخفض", "en": "Low"},
    "priority.normal": {"ar": "عادي", "en": "Normal"},
    "priority.high": {"ar": "عالي", "en": "High"},
    "priority.urgent": {"ar": "عاجل", "en": "Urgent"},

    # Admin dashboard
    "admin.dashboard_title": {"ar": "لوحة التحكم", "en": "Dashboard"},
    "admin.dashboard_subtitle": {"ar": "نظرة عامة شاملة على النظام", "en": "System overview"},
    "admin.quick_search": {"ar": "🔍 بحث سريع...", "en": "🔍 Quick search..."},
    "admin.new_request": {"ar": "+ طلب جديد", "en": "+ New Request"},
    "admin.kpi_clients": {"ar": "العملاء", "en": "Clients"},
    "admin.kpi_devices": {"ar": "الأجهزة", "en": "Devices"},
    "admin.kpi_open_requests": {"ar": "طلبات مفتوحة", "en": "Open Requests"},
    "admin.kpi_new_requests": {"ar": "طلبات جديدة", "en": "New Requests"},
    "admin.kpi_sla_breached": {"ar": "تجاوز SLA", "en": "SLA Breached"},
    "admin.kpi_surveys": {"ar": "معاينات جارية", "en": "Ongoing Surveys"},
    "admin.kpi_today": {"ar": "اليوم", "en": "Today"},
    "admin.kpi_week": {"ar": "الأسبوع", "en": "This Week"},
    "admin.kpi_closed_month": {"ar": "مغلق (30 يوم)", "en": "Closed (30d)"},
    "admin.kpi_open_tickets": {"ar": "تذاكر مفتوحة", "en": "Open Tickets"},
    "admin.kpi_technicians": {"ar": "الفنيين", "en": "Technicians"},
    "admin.kpi_qr_used": {"ar": "QR مستخدم", "en": "QR Used"},
    "admin.kpi_avg_rating": {"ar": "متوسط التقييم", "en": "Avg Rating"},
    "admin.qa_request": {"ar": "طلب صيانة", "en": "Maintenance Request"},
    "admin.qa_ticket": {"ar": "تذكرة دعم", "en": "Support Ticket"},
    "admin.qa_client": {"ar": "عميل جديد", "en": "New Client"},
    "admin.qa_device": {"ar": "جهاز جديد", "en": "New Device"},
    "admin.qa_user": {"ar": "مستخدم", "en": "User"},
    "admin.qa_scan": {"ar": "مسح QR", "en": "Scan QR"},
    "admin.qa_reports": {"ar": "التقارير", "en": "Reports"},
    "admin.qa_settings": {"ar": "الإعدادات", "en": "Settings"},
    "admin.chart_trend": {"ar": "📈 طلبات آخر 14 يوم", "en": "📈 Requests (last 14 days)"},
    "admin.chart_status": {"ar": "🎯 توزيع الحالات", "en": "🎯 Status Distribution"},
    "admin.recent_requests": {"ar": "أحدث الطلبات", "en": "Recent Requests"},
    "admin.view_all": {"ar": "عرض الكل ←", "en": "View all →"},
    "admin.col_number": {"ar": "الرقم", "en": "No."},
    "admin.col_client": {"ar": "العميل", "en": "Client"},
    "admin.col_title": {"ar": "العنوان", "en": "Title"},
    "admin.col_priority": {"ar": "الأولوية", "en": "Priority"},
    "admin.col_status": {"ar": "الحالة", "en": "Status"},
    "admin.no_requests": {"ar": "لا يوجد طلبات", "en": "No requests"},

    # Admin clients list
    "admin.clients_title": {"ar": "العملاء", "en": "Clients"},
    "admin.clients_count": {"ar": "{n} عميل", "en": "{n} clients"},
    "admin.new_client": {"ar": "+ عميل جديد", "en": "+ New Client"},
    "admin.search_clients_ph": {"ar": "بحث بالاسم، التليفون، الكود...", "en": "Search by name, phone, code..."},
    "admin.col_code": {"ar": "الكود", "en": "Code"},
    "admin.col_company": {"ar": "اسم الشركة", "en": "Company"},
    "admin.col_contact": {"ar": "المسؤول", "en": "Contact"},
    "admin.col_phone": {"ar": "التليفون", "en": "Phone"},
    "admin.col_city": {"ar": "المدينة", "en": "City"},
    "admin.col_devices": {"ar": "الأجهزة", "en": "Devices"},
    "admin.col_balance": {"ar": "الرصيد", "en": "Balance"},
    "admin.no_clients": {"ar": "لا يوجد عملاء", "en": "No clients"},
    "admin.first_client": {"ar": "+ إضافة أول عميل", "en": "+ Add first client"},
    "admin.confirm_delete_client": {"ar": "متأكد من حذف {name}؟ سيتم فصل كل المستخدمين المرتبطين.",
                                     "en": "Delete {name}? All linked users will be detached."},

    # Admin requests list
    "admin.requests_title": {"ar": "طلبات الصيانة", "en": "Maintenance Requests"},
    "badge.active": {"ar": "فعال", "en": "Active"},

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
