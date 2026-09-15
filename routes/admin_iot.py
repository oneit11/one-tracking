"""
Admin routes for IoT devices — CRUD, live view, alarms log.
Prefix: /admin/iot
"""
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required
from models import db
from models.iot_device import IoTDevice, IoTAlarm
from models.client import Client
from utils.decorators import admin_required

admin_iot_bp = Blueprint("admin_iot", __name__)


def _new_claim_code():
    """Generate a 6-digit numeric code that is unique among unclaimed devices."""
    while True:
        code = str(secrets.randbelow(900_000) + 100_000)
        if not IoTDevice.query.filter_by(claim_code=code).first():
            return code


@admin_iot_bp.route("/")
@login_required
@admin_required
def list_devices():
    devices = IoTDevice.query.order_by(IoTDevice.created_at.desc()).all()
    return render_template("admin/iot_list.html", devices=devices)


@admin_iot_bp.route("/new", methods=["GET", "POST"])
@login_required
@admin_required
def new_device():
    if request.method == "POST":
        d = IoTDevice(
            name=request.form.get("name", "").strip(),
            location=request.form.get("location", "").strip(),
            notes=request.form.get("notes", "").strip(),
            client_id=int(request.form["client_id"]) if request.form.get("client_id") else None,
            temp_min=float(request.form.get("temp_min") or 18),
            temp_max=float(request.form.get("temp_max") or 27),
            humid_min=float(request.form.get("humid_min") or 30),
            humid_max=float(request.form.get("humid_max") or 60),
            smoke_threshold=int(request.form.get("smoke_threshold") or 2000),
            claim_code=_new_claim_code(),
        )
        db.session.add(d)
        db.session.commit()
        flash(f"تم إنشاء الجهاز — كود التفعيل: {d.claim_code}", "success")
        return redirect(url_for("admin_iot.view_device", dev_id=d.id))

    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()
    return render_template("admin/iot_form.html", dev=None, clients=clients)


@admin_iot_bp.route("/<int:dev_id>")
@login_required
@admin_required
def view_device(dev_id):
    dev = IoTDevice.query.get_or_404(dev_id)
    alarms = IoTAlarm.query.filter_by(device_id=dev.id) \
        .order_by(IoTAlarm.ts.desc()).limit(30).all()
    return render_template("admin/iot_view.html", dev=dev, alarms=alarms)


@admin_iot_bp.route("/<int:dev_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_device(dev_id):
    dev = IoTDevice.query.get_or_404(dev_id)
    if request.method == "POST":
        dev.name = request.form.get("name", "").strip()
        dev.location = request.form.get("location", "").strip()
        dev.notes = request.form.get("notes", "").strip()
        dev.client_id = int(request.form["client_id"]) if request.form.get("client_id") else None
        dev.temp_min = float(request.form.get("temp_min") or 18)
        dev.temp_max = float(request.form.get("temp_max") or 27)
        dev.humid_min = float(request.form.get("humid_min") or 30)
        dev.humid_max = float(request.form.get("humid_max") or 60)
        dev.smoke_threshold = int(request.form.get("smoke_threshold") or 2000)
        dev.is_active = bool(request.form.get("is_active"))
        db.session.commit()
        flash("تم حفظ التعديلات", "success")
        return redirect(url_for("admin_iot.view_device", dev_id=dev.id))

    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()
    return render_template("admin/iot_form.html", dev=dev, clients=clients)


@admin_iot_bp.route("/<int:dev_id>/regenerate-claim", methods=["POST"])
@login_required
@admin_required
def regenerate_claim(dev_id):
    """Issue a new claim code — useful if the old one leaked or was lost.
    Also nulls the api_key so the device is forced to re-provision."""
    dev = IoTDevice.query.get_or_404(dev_id)
    dev.claim_code = _new_claim_code()
    dev.api_key = ""
    db.session.commit()
    flash(f"تم توليد كود جديد: {dev.claim_code}", "success")
    return redirect(url_for("admin_iot.view_device", dev_id=dev.id))


@admin_iot_bp.route("/<int:dev_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_device(dev_id):
    dev = IoTDevice.query.get_or_404(dev_id)
    db.session.delete(dev)
    db.session.commit()
    flash("تم حذف الجهاز", "success")
    return redirect(url_for("admin_iot.list_devices"))
