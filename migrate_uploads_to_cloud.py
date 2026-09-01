"""
One-time migration: move existing local uploads to cloud storage (Cloudinary/R2).

For every DB column that stores a file URL, this finds values that still point
at local storage (/static/uploads/...), uploads the file to the configured
cloud backend, and rewrites the URL in the database.

Safe to run more than once: rows already pointing at the cloud are skipped,
and a file that no longer exists on disk is left untouched and reported.

HOW TO RUN ON RAILWAY:
  Open the service -> ... menu -> "Run a command" (or Railway Console) and run:
      python migrate_uploads_to_cloud.py
  Make sure the CLOUDINARY_* (or R2_*) variables are set first, and run it
  BEFORE any further redeploy so the local files are still present.

It prints a summary at the end: moved / skipped / missing / failed.
"""
import os
import sys

from app import app
from models import db
from models.attachment import Attachment
from models.client import Client, AMCContract
from models.device import Device
from models.extras import Lead, Followup
from models.request import MaintenanceRequest, VisitReport
from models.user import User
from models.setting import Setting

# (Model, attribute) pairs that hold a file URL
TARGETS = [
    (Attachment, "file_url"),
    (Client, "logo_url"),
    (AMCContract, "file_url"),
    (Device, "photo_url"),
    (Lead, "photo_url"),
    (Followup, "quote_file_url"),
    (MaintenanceRequest, "submitted_photo_url"),
    (VisitReport, "photo_url"),
    (User, "avatar_url"),
]

# Settings keys that hold a file URL
SETTING_KEYS = ["logo_url", "favicon_url"]

LOCAL_PREFIX = "/static/uploads/"


def _local_path(url):
    """Map a stored /static/uploads/... URL to an absolute path on disk."""
    if not url or LOCAL_PREFIX not in url:
        return None
    # take everything after /static/uploads/
    rel = url.split(LOCAL_PREFIX, 1)[1]
    base = app.config.get("UPLOAD_FOLDER")
    return os.path.join(base, rel)


def _upload_file(path, subfolder):
    """Upload a file on disk to the cloud and return the new URL, or ''."""
    from werkzeug.datastructures import FileStorage
    from utils.helpers import save_upload, _cloudinary_config, _r2_config
    if not (_cloudinary_config() or _r2_config()):
        print("!! No cloud backend configured (CLOUDINARY_* or R2_*). Aborting.")
        sys.exit(1)
    filename = os.path.basename(path)
    with open(path, "rb") as fh:
        fs = FileStorage(stream=fh, filename=filename)
        return save_upload(fs, subfolder=subfolder)


def run():
    moved = skipped = missing = failed = 0
    with app.app_context():
        # --- model columns ---
        for model, attr in TARGETS:
            rows = model.query.all()
            for row in rows:
                url = getattr(row, attr, "") or ""
                if not url or LOCAL_PREFIX not in url:
                    skipped += 1
                    continue
                path = _local_path(url)
                if not path or not os.path.exists(path):
                    print(f"  MISSING {model.__name__}#{row.id}.{attr}: {url}")
                    missing += 1
                    continue
                subfolder = model.__tablename__
                try:
                    new_url = _upload_file(path, subfolder)
                    if new_url and LOCAL_PREFIX not in new_url:
                        setattr(row, attr, new_url)
                        db.session.commit()
                        print(f"  MOVED {model.__name__}#{row.id}.{attr}")
                        moved += 1
                    else:
                        print(f"  FAILED {model.__name__}#{row.id}.{attr} (upload returned local/empty)")
                        failed += 1
                except Exception as e:
                    db.session.rollback()
                    print(f"  FAILED {model.__name__}#{row.id}.{attr}: {str(e)[:120]}")
                    failed += 1

        # --- settings (logo / favicon) ---
        for key in SETTING_KEYS:
            s = Setting.query.filter_by(key=key).first()
            url = (s.value if s else "") or ""
            if not url or LOCAL_PREFIX not in url:
                skipped += 1
                continue
            path = _local_path(url)
            if not path or not os.path.exists(path):
                print(f"  MISSING setting {key}: {url}")
                missing += 1
                continue
            try:
                new_url = _upload_file(path, "branding")
                if new_url and LOCAL_PREFIX not in new_url:
                    Setting.set(key, new_url, "branding")
                    db.session.commit()
                    print(f"  MOVED setting {key}")
                    moved += 1
                else:
                    print(f"  FAILED setting {key} (upload returned local/empty)")
                    failed += 1
            except Exception as e:
                db.session.rollback()
                print(f"  FAILED setting {key}: {str(e)[:120]}")
                failed += 1

    print("\n==================== SUMMARY ====================")
    print(f"  moved   : {moved}")
    print(f"  skipped : {skipped}  (already cloud / empty)")
    print(f"  missing : {missing}  (file not on disk)")
    print(f"  failed  : {failed}")
    print("================================================")
    if failed:
        print("Some files failed — re-run the script to retry just those.")


if __name__ == "__main__":
    run()
