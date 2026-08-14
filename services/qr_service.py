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
    Each label includes: QR + code text + phone.
    Returns bytes.
    """
    if size not in SIZE_MAP:
        size = "medium"
    cfg = SIZE_MAP[size]
    qr_cm_size = cfg["qr_cm"]
    cols = cfg["cols"]
    rows = cfg["rows"]

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4
    margin = 1.0 * cm

    cell_w = (page_w - 2 * margin) / cols
    cell_h = (page_h - 2 * margin) / rows

    qr_px_size = qr_cm_size * cm

    idx = 0
    for qr in qr_codes:
        url = f"{app_url}/d/{qr.code}" if app_url else qr.code
        img = build_qr_image(url, box_size=6)

        # Save temp
        img_buf = io.BytesIO()
        img.save(img_buf, format="PNG")
        img_buf.seek(0)

        col = idx % cols
        row = (idx // cols) % rows
        if idx > 0 and idx % (cols * rows) == 0:
            c.showPage()

        # Cell origin (top-left of cell in PDF coords - PDF origin is bottom-left)
        cell_x = margin + col * cell_w
        cell_y = page_h - margin - (row + 1) * cell_h

        # Center QR in cell
        qr_x = cell_x + (cell_w - qr_px_size) / 2
        qr_y = cell_y + (cell_h - qr_px_size) / 2 + 4 * mm  # shift up to make room for text

        c.drawInlineImage(Image.open(img_buf), qr_x, qr_y, width=qr_px_size, height=qr_px_size)

        # Text below QR
        c.setFont("Helvetica", 6)
        text_y = qr_y - 3 * mm
        c.drawCentredString(cell_x + cell_w / 2, text_y, qr.code)
        if company_phone:
            c.drawCentredString(cell_x + cell_w / 2, text_y - 3 * mm, company_phone)

        # Light cut guide
        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.setLineWidth(0.3)
        c.rect(cell_x, cell_y, cell_w, cell_h)

        idx += 1

    c.save()
    buffer.seek(0)
    return buffer.read()
