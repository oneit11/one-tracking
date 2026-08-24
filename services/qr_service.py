"""
QR code generation and printable PDF label sheets.
Sizes: small (2cm), medium (3cm), large (5cm).
"""
import os
import io
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image
from flask import current_app


SIZE_MAP = {
    "small": {"qr_cm": 2.0, "cols": 8, "rows": 12, "label": "2×2 سم"},
    "medium": {"qr_cm": 3.0, "cols": 5, "rows": 8, "label": "3×3 سم"},
    "large": {"qr_cm": 5.0, "cols": 3, "rows": 5, "label": "5×5 سم"},
}


def build_qr_image(data, box_size=10):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def generate_qr_pdf(qr_codes, size="medium", app_url="", company_name="ONE Tracking",
                    company_phone="", include_header=True):
    """
    Generate a printable PDF sheet with QR labels for the given qr_codes.
    Each label is a bordered card with: company name on top, the QR centered,
    the code text, and "(لطلب صيانة)" at the bottom.
    Returns bytes.
    """
    # Arabic-aware font + reshaping (reuse pdf_service helpers)
    try:
        from services.pdf_service import _register_font, ar, _FONT_BOLD_NAME
        _register_font()
        from services import pdf_service as _pdf
        font_reg = _pdf._FONT_NAME or "Helvetica"
        font_bold = _pdf._FONT_BOLD_NAME or "Helvetica-Bold"
    except Exception:
        ar = lambda t: (t or "")
        font_reg, font_bold = "Helvetica", "Helvetica-Bold"

    if size not in SIZE_MAP:
        size = "medium"
    cfg = SIZE_MAP[size]
    qr_cm_size = cfg["qr_cm"]
    cols = cfg["cols"]
    rows = cfg["rows"]

    # Font scaling by label size
    scale = {"small": 0.8, "medium": 1.0, "large": 1.35}.get(size, 1.0)
    name_fs = 8 * scale
    service_fs = 7.5 * scale
    code_fs = 6 * scale

    service_txt = ar("(لطلب صيانة)")
    name_txt = ar(company_name or "")

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4
    margin = 1.0 * cm

    cell_w = (page_w - 2 * margin) / cols
    cell_h = (page_h - 2 * margin) / rows

    pad = 2.0 * mm          # inner padding inside the border
    gap = 1.2 * mm          # gap between text and QR

    idx = 0
    for qr in qr_codes:
        url = f"{app_url}/d/{qr.code}" if app_url else qr.code
        img = build_qr_image(url, box_size=6)
        img_buf = io.BytesIO()
        img.save(img_buf, format="PNG")
        img_buf.seek(0)

        col = idx % cols
        row = (idx // cols) % rows
        if idx > 0 and idx % (cols * rows) == 0:
            c.showPage()

        cell_x = margin + col * cell_w
        cell_y = page_h - margin - (row + 1) * cell_h
        cx = cell_x + cell_w / 2

        # ---- Card border (تحديد) ----
        c.setStrokeColorRGB(0.13, 0.13, 0.13)
        c.setLineWidth(1.1)
        c.roundRect(cell_x + 1.2 * mm, cell_y + 1.2 * mm,
                    cell_w - 2.4 * mm, cell_h - 2.4 * mm, 3 * mm, stroke=1, fill=0)

        inner_top = cell_y + cell_h - pad - 1.2 * mm
        inner_bottom = cell_y + pad + 1.2 * mm

        # ---- Company name (top) — auto-shrink to fit card width ----
        c.setFillColorRGB(0, 0, 0)
        max_name_w = cell_w - 2 * (pad + 2.4 * mm)
        fs = name_fs
        while fs > 4.5 and c.stringWidth(name_txt, font_bold, fs) > max_name_w:
            fs -= 0.3
        c.setFont(font_bold, fs)
        name_y = inner_top - fs * 0.9
        c.drawCentredString(cx, name_y, name_txt)

        # ---- Service caption (bottom) ----
        c.setFont(font_reg, service_fs)
        service_y = inner_bottom + code_fs + 1.2 * mm
        c.drawCentredString(cx, service_y, service_txt)

        # ---- Code text (very bottom) ----
        c.setFont("Helvetica", code_fs)
        c.setFillColorRGB(0.35, 0.35, 0.35)
        c.drawCentredString(cx, inner_bottom, qr.code)
        c.setFillColorRGB(0, 0, 0)

        # ---- QR (centered between name and caption) ----
        avail_top = name_y - gap
        avail_bottom = service_y + service_fs * 0.5 + gap
        avail_h = avail_top - avail_bottom
        avail_w = cell_w - 2 * (pad + 1.2 * mm)
        qr_side = min(qr_cm_size * cm, avail_h, avail_w)
        qr_x = cx - qr_side / 2
        qr_y = avail_bottom + (avail_h - qr_side) / 2
        c.drawInlineImage(Image.open(img_buf), qr_x, qr_y, width=qr_side, height=qr_side)

        idx += 1

    c.save()
    buffer.seek(0)
    return buffer.read()
