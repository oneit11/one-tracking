from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import all models so create_all picks them up
from models.user import User  # noqa: E402
from models.client import Client, AMCContract, AccountEntry  # noqa: E402
from models.device import Device, QRBatch, QRCode  # noqa: E402
from models.request import (  # noqa: E402
    MaintenanceRequest, VisitReport, SupportTicket, ProjectMember, ProjectVisit,
)
from models.attachment import Attachment  # noqa: E402
from models.wa_log import WhatsAppLog  # noqa: E402
from models.setting import Setting, MessageTemplate  # noqa: E402
from models.permission import Role, UserPermissionOverride  # noqa: E402
from models.extras import (  # noqa: E402
    Notification, AuditLog, Comment, Rating,
    SparePart, StockMovement, PMSchedule, Followup, Lead,
    Survey, SurveyItem,
)
