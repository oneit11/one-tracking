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


def _r2_config():
    """Return R2/S3 config dict if all required env vars are set, else None."""
    cfg = {
        "access_key": os.getenv("R2_ACCESS_KEY_ID", ""),
        "secret_key": os.getenv("R2_SECRET_ACCESS_KEY", ""),
        "endpoint": os.getenv("R2_ENDPOINT", ""),
        "bucket": os.getenv("R2_BUCKET", ""),
        "public_url": os.getenv("R2_PUBLIC_URL", "").rstrip("/"),
    }
    if all([cfg["access_key"], cfg["secret_key"], cfg["endpoint"],
            cfg["bucket"], cfg["public_url"]]):
        return cfg
    return None


def _upload_to_r2(file_storage, key, cfg):
    """Upload a file object to Cloudflare R2 (S3-compatible). Returns public URL or ''."""
    try:
        import boto3  # noqa: F401
        from botocore.config import Config as _BotoConfig
    except ImportError:
        current_app.logger.warning("boto3 not installed — falling back to local upload")
        return ""
    try:
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=cfg["endpoint"],
            aws_access_key_id=cfg["access_key"],
            aws_secret_access_key=cfg["secret_key"],
            config=_BotoConfig(signature_version="s3v4"),
            region_name="auto",
        )
        content_type = getattr(file_storage, "mimetype", None) or "application/octet-stream"
        file_storage.stream.seek(0)
        client.upload_fileobj(
            file_storage.stream, cfg["bucket"], key,
            ExtraArgs={"ContentType": content_type},
        )
        return f"{cfg['public_url']}/{key}"
    except Exception as e:
        current_app.logger.error(f"R2 upload failed: {str(e)[:150]}")
        return ""


def _cloudinary_config():
    """Return Cloudinary config if all required env vars are set, else None."""
    cfg = {
        "cloud_name": os.getenv("CLOUDINARY_CLOUD_NAME", ""),
        "api_key": os.getenv("CLOUDINARY_API_KEY", ""),
        "api_secret": os.getenv("CLOUDINARY_API_SECRET", ""),
    }
    if all(cfg.values()):
        return cfg
    return None


def _upload_to_cloudinary(file_storage, key, cfg):
    """Upload to Cloudinary. Returns secure URL or ''."""
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError:
        current_app.logger.warning("cloudinary not installed — falling back")
        return ""
    try:
        cloudinary.config(
            cloud_name=cfg["cloud_name"],
            api_key=cfg["api_key"],
            api_secret=cfg["api_secret"],
            secure=True,
        )
        file_storage.stream.seek(0)
        # PDFs and non-images go as "raw"; images auto-optimised
        ext = (file_storage.filename.rsplit(".", 1)[-1] or "").lower()
        resource_type = "image" if ext in {"png", "jpg", "jpeg", "gif", "webp"} else "raw"
        folder = os.getenv("CLOUDINARY_FOLDER", "one-tracking")
        result = cloudinary.uploader.upload(
            file_storage.stream,
            public_id=key.rsplit(".", 1)[0],
            folder=folder,
            resource_type=resource_type,
            overwrite=True,
        )
        return result.get("secure_url", "")
    except Exception as e:
        current_app.logger.error(f"Cloudinary upload failed: {str(e)[:150]}")
        return ""


def save_upload(file_storage, subfolder="", prefix=""):
    """Save an uploaded file and return its URL.

    Storage backend is chosen automatically by which env vars are set:
      1. Cloudinary  (CLOUDINARY_CLOUD_NAME / API_KEY / API_SECRET)
      2. Cloudflare R2  (R2_* vars)
      3. Local disk  (default fallback — original behaviour)
    """
    if not file_storage or not file_storage.filename:
        return ""
    if not allowed_file(file_storage.filename):
        return ""
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    unique = secure_filename(f"{prefix}{uuid.uuid4().hex[:12]}.{ext}")
    key = f"{subfolder}/{unique}" if subfolder else unique
    key = key.replace("\\", "/").lstrip("/")

    # ---- Cloudinary ----
    ccfg = _cloudinary_config()
    if ccfg:
        url = _upload_to_cloudinary(file_storage, key, ccfg)
        if url:
            return url

    # ---- Cloudflare R2 ----
    cfg = _r2_config()
    if cfg:
        url = _upload_to_r2(file_storage, key, cfg)
        if url:
            return url

    # ---- Local disk (fallback / default) ----
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], subfolder)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, unique)
    file_storage.stream.seek(0)
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


def is_valid_eg_mobile(phone):
    """True if `phone` is a valid Egyptian mobile number.

    Accepts common formats (01xxxxxxxxx, +2001..., 201..., 1x...) and checks
    it resolves to an 11-digit local number starting with 010/011/012/015.
    """
    if not phone:
        return False
    p = re.sub(r"[^\d+]", "", str(phone))
    # strip country code to a local 0-prefixed form
    if p.startswith("+20"):
        p = "0" + p[3:]
    elif p.startswith("0020"):
        p = "0" + p[4:]
    elif p.startswith("20") and len(p) == 12:
        p = "0" + p[2:]
    elif len(p) == 10 and p.startswith("1"):
        p = "0" + p
    # now expect 11 digits: 01[0125]xxxxxxxx
    return bool(re.fullmatch(r"01[0125]\d{8}", p))


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
