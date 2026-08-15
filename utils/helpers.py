import os
import re
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app


def allowed_file(filename):
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def save_upload(file_storage, subfolder="", prefix=""):
    """Save uploaded file with unique name. Returns relative URL from /static/uploads/."""
    if not file_storage or not file_storage.filename:
        return ""
    if not allowed_file(file_storage.filename):
        return ""
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    unique = f"{prefix}{uuid.uuid4().hex[:12]}.{ext}"
    unique = secure_filename(unique)
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], subfolder)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, unique)
    file_storage.save(path)
    rel = f"/static/uploads/{subfolder}/{unique}" if subfolder else f"/static/uploads/{unique}"
    return rel.replace("\\", "/").replace("//", "/")


def next_sequence(model, field, prefix):
    """Generate next sequential ID like MR26-0001."""
    from models import db
    year_suffix = datetime.utcnow().strftime("%y")
    pattern = f"{prefix}{year_suffix}-"
    last = db.session.query(model).filter(
        getattr(model, field).like(f"{pattern}%")
    ).order_by(getattr(model, field).desc()).first()
    if not last:
        return f"{pattern}0001"
    val = getattr(last, field)
    try:
        num = int(val.split("-")[-1]) + 1
    except (ValueError, IndexError):
        num = 1
    return f"{pattern}{num:04d}"


def normalize_phone(phone):
    """Normalize Egyptian phone numbers to +20XXXXXXXXXX (WA format)."""
    if not phone:
        return ""
    p = re.sub(r"[^\d+]", "", str(phone))
    if p.startswith("+"):
        return p
    if p.startswith("00"):
        return "+" + p[2:]
    if p.startswith("20"):
        return "+" + p
    if p.startswith("0"):
        return "+20" + p[1:]
    if len(p) == 10 and p.startswith("1"):
        return "+20" + p
    return "+" + p


def format_datetime(dt, fmt="%Y-%m-%d %H:%M"):
    if not dt:
        return ""
    return dt.strftime(fmt)


def next_qr_batch_code():
    from models import db
    from models.device import QRBatch
    year = datetime.utcnow().strftime("%Y")
    prefix = f"BATCH-{year}-"
    last = db.session.query(QRBatch).filter(
        QRBatch.batch_code.like(f"{prefix}%")
    ).order_by(QRBatch.batch_code.desc()).first()
    num = 1
    if last and last.batch_code:
        try:
            num = int(last.batch_code.split("-")[-1]) + 1
        except (ValueError, IndexError):
            num = 1
    return f"{prefix}{num:04d}"


def next_qr_code(index):
    year = datetime.utcnow().strftime("%Y")
    return f"ONE-QR-{year}-{index:06d}"


def next_client_code():
    from models import db
    from models.client import Client
    last = db.session.query(Client).order_by(Client.id.desc()).first()
    num = (last.id + 1) if last else 1
    return f"CL-{num:06d}"
