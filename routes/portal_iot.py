"""
Client-facing IoT views inside the customer portal.
Prefix: /portal/iot
"""
from flask import Blueprint, render_template, abort, redirect, url_for
from flask_login import login_required, current_user
from models.iot_device import IoTDevice, IoTAlarm
from utils.decorators import client_required

portal_iot_bp = Blueprint("portal_iot", __name__)


@portal_iot_bp.route("/")
@client_required
def dashboard():
    if not current_user.client_id:
        return redirect(url_for("portal.dashboard"))
    devices = IoTDevice.query.filter_by(client_id=current_user.client_id) \
        .order_by(IoTDevice.name).all()
    return render_template("portal/iot_dashboard.html", devices=devices)


@portal_iot_bp.route("/<int:dev_id>")
@client_required
def device_view(dev_id):
    dev = IoTDevice.query.get_or_404(dev_id)
    if dev.client_id != current_user.client_id:
        abort(403)
    alarms = IoTAlarm.query.filter_by(device_id=dev.id) \
        .order_by(IoTAlarm.ts.desc()).limit(20).all()
    return render_template("portal/iot_device.html", dev=dev, alarms=alarms)
