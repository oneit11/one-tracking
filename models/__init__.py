from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import all models so create_all picks them up
from models.user import User  # noqa: E402
from models.client import Client, AMCContract  # noqa: E402
from models.device import Device, QRBatch, QRCode  # noqa: E402
from models.request import MaintenanceRequest, VisitReport, SupportTicket  # noqa: E402
from models.attachment import Attachment  # noqa: E402
from models.wa_log import WhatsAppLog  # noqa: E402
