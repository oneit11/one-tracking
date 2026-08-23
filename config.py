import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Core
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    APP_NAME = os.getenv("APP_NAME", "ONE Tracking")
    APP_URL = os.getenv("APP_URL", "http://localhost:5000")
    COMPANY_NAME = os.getenv("COMPANY_NAME", "ONE For Integrated Solutions")
    COMPANY_PHONE = os.getenv("COMPANY_PHONE", "01220733003")
    COMPANY_EMAIL = os.getenv("COMPANY_EMAIL", "info@one4in.com")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "onetracking.db"))
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}

    # Uploads
    # On Railway (or any ephemeral host) set UPLOAD_FOLDER to a mounted volume
    # path (e.g. /data/uploads) so uploaded logos/photos survive redeploys.
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(BASE_DIR, "static", "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "128")) * 1024 * 1024  # 128 MB (videos)
    ALLOWED_EXTENSIONS = {
        # images
        "png", "jpg", "jpeg", "gif", "webp", "heic", "heif", "bmp",
        # videos
        "mp4", "mov", "webm", "avi", "mkv", "3gp", "m4v", "quicktime",
        # docs
        "pdf", "docx", "xlsx", "doc", "xls",
    }
    VIDEO_EXTENSIONS = {"mp4", "mov", "webm", "avi", "mkv", "3gp", "m4v", "quicktime"}

    # WhatsApp (Baileys sidecar)
    WA_ENABLED = os.getenv("WA_ENABLED", "false").lower() == "true"
    WA_SIDECAR_URL = os.getenv("WA_SIDECAR_URL", "")
    WA_SIDECAR_API_KEY = os.getenv("WA_SIDECAR_API_KEY", "")

    # Emergency migration
    EMERGENCY_MIGRATE_SECRET = os.getenv("EMERGENCY_MIGRATE_SECRET", "ONE-Tracking-Emergency-2026")

    # Default admin
    DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@one4in.com")
    DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "ChangeMe@2026")
    DEFAULT_ADMIN_NAME = os.getenv("DEFAULT_ADMIN_NAME", "Ehab Mohamed")

    # Language
    DEFAULT_LANG = os.getenv("DEFAULT_LANG", "ar")
