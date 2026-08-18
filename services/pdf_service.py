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
                 company_email="", logo_url="", landscape_mode=False,
                 primary_color="#0b3d91"):
        self.title = title
        self.subtitle = subtitle
        self.company_name = company_name
        self.company_phone = company_phone
        self.company_email = company_email
        self.logo_url = logo_url
        self.primary_color = colors.HexColor(primary_color)

        self.font_name = _register_font()
        self.buffer = io.BytesIO()
        self.pagesize = landscape(A4) if landscape_mode else A4
        self.elements = []

        self._build_styles()

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
        canvas.saveState()
        w, h = self.pagesize

        # Header band
        canvas.setFillColor(self.primary_color)
        canvas.rect(0, h - 1.6 * cm, w, 1.6 * cm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont(self.font_name, 14)
        canvas.drawRightString(w - 1 * cm, h - 1 * cm, ar(self.company_name or ""))
        canvas.setFont(self.font_name, 9)
        contact = f"{self.company_phone or ''}  |  {self.company_email or ''}"
        canvas.drawString(1 * cm, h - 1 * cm, ar(contact))

        # Footer
        canvas.setFillColor(colors.grey)
        canvas.setFont(self.font_name, 8)
        canvas.drawCentredString(w / 2, 0.8 * cm,
                                 ar(f"صفحة {doc.page}  ·  {datetime.now().strftime('%Y-%m-%d %H:%M')}"))
        canvas.setStrokeColor(colors.HexColor("#e5e7eb"))
        canvas.line(1 * cm, 1.2 * cm, w - 1 * cm, 1.2 * cm)

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

    def page_break(self):
        self.elements.append(PageBreak())

    def build(self):
        doc = SimpleDocTemplate(
            self.buffer, pagesize=self.pagesize,
            topMargin=2.2 * cm, bottomMargin=1.8 * cm,
            leftMargin=1 * cm, rightMargin=1 * cm,
        )
        self.add_title()
        # Build once
        doc.build(self.elements, onFirstPage=self._header_footer,
                  onLaterPages=self._header_footer)
        self.buffer.seek(0)
        return self.buffer.read()



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
                 company_email="", logo_url="", landscape_mode=False,
                 primary_color="#0b3d91"):
        self.title = title
        self.subtitle = subtitle
        self.company_name = company_name
        self.company_phone = company_phone
        self.company_email = company_email
        self.logo_url = logo_url
        self.primary_color = colors.HexColor(primary_color)

        self.font_name = _register_font()
        self.buffer = io.BytesIO()
        self.pagesize = landscape(A4) if landscape_mode else A4
        self.elements = []

        self._build_styles()

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
        canvas.saveState()
        w, h = self.pagesize

        # Header band
        canvas.setFillColor(self.primary_color)
        canvas.rect(0, h - 1.6 * cm, w, 1.6 * cm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont(self.font_name, 14)
        canvas.drawRightString(w - 1 * cm, h - 1 * cm, ar(self.company_name or ""))
        canvas.setFont(self.font_name, 9)
        contact = f"{self.company_phone or ''}  |  {self.company_email or ''}"
        canvas.drawString(1 * cm, h - 1 * cm, ar(contact))

        # Footer
        canvas.setFillColor(colors.grey)
        canvas.setFont(self.font_name, 8)
        canvas.drawCentredString(w / 2, 0.8 * cm,
                                 ar(f"صفحة {doc.page}  ·  {datetime.now().strftime('%Y-%m-%d %H:%M')}"))
        canvas.setStrokeColor(colors.HexColor("#e5e7eb"))
        canvas.line(1 * cm, 1.2 * cm, w - 1 * cm, 1.2 * cm)

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

    def page_break(self):
        self.elements.append(PageBreak())

    def build(self):
        doc = SimpleDocTemplate(
            self.buffer, pagesize=self.pagesize,
            topMargin=2.2 * cm, bottomMargin=1.8 * cm,
            leftMargin=1 * cm, rightMargin=1 * cm,
        )
        self.add_title()
        # Build once
        doc.build(self.elements, onFirstPage=self._header_footer,
                  onLaterPages=self._header_footer)
        self.buffer.seek(0)
        return self.buffer.read()
