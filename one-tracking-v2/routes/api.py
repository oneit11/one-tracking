from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required
from sqlalchemy import desc
from models import db
from models.request import MaintenanceRequest
from models.device import Device

api_bp = Blueprint("api", __name__)


@api_bp.route("/devices/<int:did>/client")
@login_required
def device_client(did):
    """Fetch client_id for a device — used by request form JS."""
    d = Device.query.get_or_404(did)
    return jsonify({"client_id": d.client_id, "name": d.name})


@api_bp.route("/clients/<int:cid>/devices")
@login_required
def client_devices(cid):
    devices = Device.query.filter_by(client_id=cid, active=True).all()
    return jsonify([{"id": d.id, "name": d.name, "location": d.location} for d in devices])
