"""
Professional PDF report generator with Arabic RTL support.
Uses reportlab + arabic-reshaper + python-bidi for correct text rendering.
"""
import io
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import arabic_reshaper
from bidi.algorithm import get_display


# Register Arabic font (fallback to Helvetica if not found)
_FONT_NAME = None
_FONT_BOLD_NAME = None


def _register_font():
    """Register bundled Amiri fonts (Arabic-optimized). Falls back to system fonts."""
    global _FONT_NAME, _FONT_BOLD_NAME
    if _FONT_NAME:
        return _FONT_NAME
    try:
        # Look for bundled fonts in static/fonts/ (relative to app root)
        # __file__ is services/pdf_service.py → parent is services → parent is app root
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates_reg = [
            os.path.join(app_root, "static", "fonts", "Amiri-Regular.ttf"),
            os.path.join(app_root, "static", "fonts", "DejaVuSans.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
        candidates_bold = [
            os.path.join(app_root, "static", "fonts", "Amiri-Bold.ttf"),
            os.path.join(app_root, "static", "fonts", "DejaVuSans.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]

        for path in candidates_reg:
            if os.path.exists(path):
                pdfmetrics.registerFont(TTFont("Arabic", path))
                _FONT_NAME = "Arabic"
                break

        for path in candidates_bold:
            if os.path.exists(path):
                pdfmetrics.registerFont(TTFont("Arabic-Bold", path))
                _FONT_BOLD_NAME = "Arabic-Bold"
                break

        if _FONT_NAME:
            return _FONT_NAME
    except Exception as e:
        print(f"Font registration failed: {e}")
    _FONT_NAME = "Helvetica"
    _FONT_BOLD_NAME = "Helvetica-Bold"
    return _FONT_NAME


def ar(text):
    """Reshape Arabic text for correct RTL display."""
    if not text:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except Exception:
        return str(text)


class PDFReport:
    def __init__(self, title, subtitle="", company_name="", company_phone="",
                 company_email="", company_phone_alt="", logo_url="",
                 landscape_mode=False, primary_color="#0b3d91"):
        self.title = title
        self.subtitle = subtitle
        self.company_name = company_name
        self.company_phone = company_phone
        self.company_phone_alt = company_phone_alt
        self.company_email = company_email
        self.logo_url = logo_url
        self.primary_color = colors.HexColor(primary_color)

        self.font_name = _register_font()
        self.buffer = io.BytesIO()
        self.pagesize = landscape(A4) if landscape_mode else A4
        self.elements = []
        self.gold = colors.HexColor("#c9a227")

        # Branded banner image (top of report)
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        banner = os.path.join(app_root, "static", "img", "report", "banner.jpg")
        self.banner_path = banner if os.path.isfile(banner) else None

        self._build_styles()

    def _banner_flowable(self):
        """Full-width branded banner image, or None if missing."""
        if not self.banner_path:
            return None
        try:
            from reportlab.lib.utils import ImageReader
            ir = ImageReader(self.banner_path)
            iw, ih = ir.getSize()
            w, _h = self.pagesize
            usable = w - 2 * cm
            return Image(self.banner_path, width=usable, height=usable * ih / iw)
        except Exception:
            return None

    def _build_styles(self):
        self.styles = getSampleStyleSheet()
        self.title_style = ParagraphStyle(
            "TitleStyle", parent=self.styles["Title"],
            fontName=self.font_name, fontSize=20, alignment=TA_CENTER,
            textColor=self.primary_color, spaceAfter=6,
        )
        self.subtitle_style = ParagraphStyle(
            "SubStyle", parent=self.styles["Normal"],
            fontName=self.font_name, fontSize=12, alignment=TA_CENTER,
            textColor=colors.grey, spaceAfter=14,
        )
        self.header_style = ParagraphStyle(
            "HeaderStyle", parent=self.styles["Heading2"],
            fontName=self.font_name, fontSize=14, alignment=TA_RIGHT,
            textColor=self.primary_color, spaceBefore=8, spaceAfter=6,
        )
        self.body_style = ParagraphStyle(
            "BodyRTL", parent=self.styles["Normal"],
            fontName=self.font_name, fontSize=10, alignment=TA_RIGHT,
        )
        self.small_style = ParagraphStyle(
            "Small", parent=self.styles["Normal"],
            fontName=self.font_name, fontSize=8, alignment=TA_CENTER,
            textColor=colors.grey,
        )

    def _header_footer(self, canvas, doc):
        """Branded contact bar at the bottom of every page (banner is a flowable at top)."""
        canvas.saveState()
        w, h = self.pagesize

        # Bottom contact bar (navy) with a thin gold accent line above it
        bar_h = 1.0 * cm
        canvas.setFillColor(self.primary_color)
        canvas.rect(0, 0, w, bar_h, stroke=0, fill=1)
        canvas.setFillColor(self.gold)
        canvas.rect(0, bar_h, w, 0.05 * cm, stroke=0, fill=1)

        contact = "   |   ".join(
            p for p in [self.company_phone, self.company_phone_alt, self.company_email] if p
        )
        canvas.setFillColor(colors.white)
        canvas.setFont(self.font_name, 9)
        canvas.drawCentredString(w / 2, 0.36 * cm, contact)

        # Page number + timestamp just above the bar
        canvas.setFillColor(colors.grey)
        canvas.setFont(self.font_name, 8)
        canvas.drawRightString(w - 1 * cm, bar_h + 0.2 * cm, ar(f"صفحة {doc.page}"))
        canvas.drawString(1 * cm, bar_h + 0.2 * cm, datetime.now().strftime('%Y-%m-%d %H:%M'))

        canvas.restoreState()

    def add_title(self):
        self.elements.append(Paragraph(ar(self.title), self.title_style))
        if self.subtitle:
            self.elements.append(Paragraph(ar(self.subtitle), self.subtitle_style))
        self.elements.append(Spacer(1, 6))

    def add_heading(self, text):
        self.elements.append(Spacer(1, 8))
        self.elements.append(Paragraph(ar(text), self.header_style))

    def add_paragraph(self, text):
        self.elements.append(Paragraph(ar(text), self.body_style))

    def add_spacer(self, h=10):
        self.elements.append(Spacer(1, h))

    def add_table(self, headers, rows, col_widths=None):
        """Add a data table. headers=[str], rows=[[str,...]]."""
        data = [[Paragraph(ar(str(h)), ParagraphStyle(
            "th", fontName=self.font_name, fontSize=10, textColor=colors.white, alignment=TA_CENTER
        )) for h in headers]]
        for row in rows:
            data.append([
                Paragraph(ar(str(cell) if cell is not None else ""),
                          ParagraphStyle("td", fontName=self.font_name, fontSize=9, alignment=TA_RIGHT))
                for cell in row
            ])

        # Reverse for RTL layout (rightmost column first visually)
        data = [list(reversed(row)) for row in data]

        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), self.primary_color),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, -1), self.font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        self.elements.append(t)
        self.elements.append(Spacer(1, 8))

    def add_key_value_table(self, pairs):
        """Two-column table for key/value details."""
        data = [
            [Paragraph(ar(str(v) if v is not None else ""),
                       ParagraphStyle("v", fontName=self.font_name, fontSize=10, alignment=TA_RIGHT)),
             Paragraph(ar(str(k)),
                       ParagraphStyle("k", fontName=self.font_name, fontSize=10,
                                      textColor=colors.grey, alignment=TA_RIGHT))]
            for k, v in pairs
        ]
        t = Table(data, colWidths=[12 * cm, 5 * cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), self.font_name),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#f1f5f9")),
        ]))
        self.elements.append(t)
        self.elements.append(Spacer(1, 8))

    def add_image(self, file_path, max_w_cm=8, max_h_cm=8):
        """Embed an image scaled to fit within the given box."""
        try:
            from reportlab.lib.utils import ImageReader
            img = ImageReader(file_path)
            iw, ih = img.getSize()
            if iw <= 0 or ih <= 0:
                return
            max_w = max_w_cm * cm
            max_h = max_h_cm * cm
            ratio = min(max_w / iw, max_h / ih)
            self.elements.append(Image(file_path, width=iw * ratio, height=ih * ratio))
            self.elements.append(Spacer(1, 6))
        except Exception:
            pass

    def add_image_grid(self, file_paths, cols=2, cell_w_cm=8, cell_h_cm=6):
        """Lay out images in a grid table so several fit per page."""
        from reportlab.lib.utils import ImageReader
        cells = []
        for p in file_paths:
            try:
                img = ImageReader(p)
                iw, ih = img.getSize()
                if iw <= 0 or ih <= 0:
                    continue
                max_w = cell_w_cm * cm
                max_h = cell_h_cm * cm
                ratio = min(max_w / iw, max_h / ih)
                cells.append(Image(p, width=iw * ratio, height=ih * ratio))
            except Exception:
                continue
        if not cells:
            return
        rows = []
        for i in range(0, len(cells), cols):
            row = cells[i:i + cols]
            while len(row) < cols:
                row.append("")
            rows.append(row)
        t = Table(rows, colWidths=[cell_w_cm * cm] * cols)
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        self.elements.append(t)
        self.elements.append(Spacer(1, 8))

    def page_break(self):
        self.elements.append(PageBreak())

    def build(self):
        doc = SimpleDocTemplate(
            self.buffer, pagesize=self.pagesize,
            topMargin=1 * cm, bottomMargin=1.6 * cm,
            leftMargin=1 * cm, rightMargin=1 * cm,
        )
        w, _h = self.pagesize
        head_els = []
        # Branded banner at the very top
        banner = self._banner_flowable()
        if banner is not None:
            head_els.append(banner)
            head_els.append(Spacer(1, 14))
        # Title + subtitle
        head_els.append(Paragraph(ar(self.title), self.title_style))
        if self.subtitle:
            head_els.append(Paragraph(ar(self.subtitle), self.subtitle_style))
        # Gold divider under the title
        divider = Table([[""]], colWidths=[w - 2 * cm])
        divider.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1.5, self.gold)]))
        head_els.append(divider)
        head_els.append(Spacer(1, 12))

        self.elements = head_els + self.elements

        doc.build(self.elements, onFirstPage=self._header_footer,
                  onLaterPages=self._header_footer)
        self.buffer.seek(0)
        return self.buffer.read()


def _resolve_upload_path(file_url, upload_folder):
    """Map a stored /static/uploads/... URL to a real filesystem path."""
    if not file_url:
        return None
    marker = "/static/uploads/"
    if marker in file_url:
        rel = file_url.split(marker, 1)[1]
    else:
        rel = file_url.lstrip("/")
    path = os.path.join(upload_folder, rel)
    return path if os.path.isfile(path) else None


def generate_project_report(project, company_name="", company_phone="",
                            company_phone_alt="", company_email="",
                            logo_url="", upload_folder=""):
    """Final project report: details + team + every visit + all photos."""
    pdf = PDFReport(
        title=f"التقرير النهائي للمشروع — {project.ticket_number}",
        subtitle=project.subject or "",
        company_name=company_name, company_phone=company_phone,
        company_phone_alt=company_phone_alt, company_email=company_email,
        logo_url=logo_url,
    )

    # Project details
    pdf.add_heading("بيانات المشروع")
    lead = project.assignee
    team_names = "، ".join(u.name for u in project.team_users) or "-"
    pdf.add_key_value_table([
        ("العميل", project.client.company_name if project.client else "-"),
        ("رقم المشروع", project.ticket_number),
        ("الموضوع", project.subject),
        ("الحالة", project.status_label),
        ("تاريخ البداية", project.start_date.strftime("%Y-%m-%d") if project.start_date else "-"),
        ("قائد الفريق", lead.name if lead else "-"),
        ("الفريق", team_names),
        ("عدد الزيارات", str(len(project.visits))),
        ("تاريخ الإغلاق", project.closed_at.strftime("%Y-%m-%d %H:%M") if project.closed_at else "-"),
    ])
    if project.description:
        pdf.add_heading("وصف المشروع")
        pdf.add_paragraph(project.description)

    # Visits
    visits = list(project.visits)
    if not visits:
        pdf.add_heading("الزيارات")
        pdf.add_paragraph("لا توجد زيارات مسجلة.")
    else:
        for idx, v in enumerate(visits, 1):
            pdf.add_heading(f"زيارة {idx} — {v.visit_date.strftime('%Y-%m-%d %H:%M')}")
            pdf.add_key_value_table([
                ("الفني", v.technician_name or (v.technician.name if v.technician else "-")),
                ("التاريخ", v.visit_date.strftime("%Y-%m-%d %H:%M")),
            ])
            if v.work_done:
                pdf.add_paragraph("العمل المنفذ: " + v.work_done)
            if v.notes:
                pdf.add_paragraph("ملاحظات: " + v.notes)
            # Photos for this visit
            paths = []
            for ph in v.photos:
                p = _resolve_upload_path(ph.file_url, upload_folder)
                if p:
                    paths.append(p)
            if paths:
                pdf.add_paragraph(f"الصور ({len(paths)}):")
                pdf.add_image_grid(paths, cols=2, cell_w_cm=8, cell_h_cm=6)

    return pdf.build()
