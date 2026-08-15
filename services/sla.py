"""SLA management - computes due dates based on priority."""
from datetime import datetime, timedelta
from services.settings_service import get_setting


def compute_sla_due(created_at, priority):
    """Return datetime when SLA is due, based on priority."""
    hours_map = {
        "urgent": int(get_setting("sla_urgent_hours", "2")),
        "high": int(get_setting("sla_high_hours", "8")),
        "normal": int(get_setting("sla_normal_hours", "24")),
        "low": int(get_setting("sla_low_hours", "72")),
    }
    hours = hours_map.get(priority, 24)
    return created_at + timedelta(hours=hours)


def check_and_flag_breach(request):
    """Check if request has breached SLA (and it's still open). Updates flag."""
    if request.status == "closed":
        return False
    if not request.sla_due_at:
        return False
    now = datetime.utcnow()
    if now > request.sla_due_at:
        request.sla_breached = True
        return True
    return False


def sla_status(request):
    """Returns one of: 'ok', 'warning', 'breached', 'na'."""
    if request.status == "closed" or not request.sla_due_at:
        return "na"
    now = datetime.utcnow()
    if now > request.sla_due_at:
        return "breached"
    remaining = (request.sla_due_at - now).total_seconds()
    # Warning if less than 25% time remaining
    total = (request.sla_due_at - request.created_at).total_seconds()
    if total > 0 and (remaining / total) < 0.25:
        return "warning"
    return "ok"


def format_time_remaining(due):
    """Human-readable time remaining/overdue."""
    if not due:
        return "-"
    now = datetime.utcnow()
    delta = due - now
    secs = int(delta.total_seconds())
    if secs < 0:
        secs = -secs
        hours = secs // 3600
        return f"متأخر {hours} ساعة" if hours >= 1 else f"متأخر {secs // 60} دقيقة"
    hours = secs // 3600
    return f"{hours} ساعة متبقية" if hours >= 1 else f"{secs // 60} دقيقة"
