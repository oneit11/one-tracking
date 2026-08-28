"""Client account / statement service.

Keeps a running ledger (AccountEntry) per client:
  - charge  = money the client owes (visit cost / manual invoice)
  - payment = money the client has paid

Balance = sum(charges) - sum(payments). Positive means the client owes us.
When a client has block_on_overdue enabled and their balance passes the
credit_limit, they cannot open a new maintenance request.
"""
from models import db
from models.client import Client, AccountEntry


def add_charge(client_id, amount, description="", request_id=None,
               source="manual", created_by=None):
    """Add a charge (invoice) to a client's account. Returns the entry or None."""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    entry = AccountEntry(
        client_id=client_id,
        entry_type="charge",
        amount=amount,
        description=description or "",
        request_id=request_id,
        source=source,
        created_by=created_by,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def add_payment(client_id, amount, description="", method="",
                created_by=None):
    """Record a payment received from a client. Returns the entry or None."""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    entry = AccountEntry(
        client_id=client_id,
        entry_type="payment",
        amount=amount,
        description=description or "",
        source="payment",
        method=method or "",
        created_by=created_by,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def sync_visit_charge(req, created_by=None):
    """Create / update / remove the auto charge tied to a maintenance request.

    Called whenever a request's visit_cost changes (on close or edit). Keeps a
    single 'visit' charge entry in sync with req.visit_cost so admins can edit
    or clear the cost later and the account stays correct.
    """
    if not req or not req.client_id:
        return None

    existing = AccountEntry.query.filter_by(
        request_id=req.id, source="visit", entry_type="charge"
    ).first()

    cost = req.visit_cost
    try:
        cost = float(cost) if cost is not None else 0
    except (TypeError, ValueError):
        cost = 0

    desc = f"تكلفة زيارة — طلب {req.request_number}"

    if cost > 0:
        if existing:
            existing.amount = cost
            existing.description = desc
        else:
            existing = AccountEntry(
                client_id=req.client_id,
                entry_type="charge",
                amount=cost,
                description=desc,
                request_id=req.id,
                source="visit",
                created_by=created_by,
            )
            db.session.add(existing)
        db.session.commit()
        return existing

    # cost is 0 / cleared -> remove the auto charge if present
    if existing:
        db.session.delete(existing)
        db.session.commit()
    return None


def delete_entry(entry_id):
    """Delete a single ledger entry. Returns True on success."""
    entry = AccountEntry.query.get(entry_id)
    if not entry:
        return False
    db.session.delete(entry)
    db.session.commit()
    return True


def can_place_request(client):
    """Return (allowed: bool, message: str). Message is shown to the client
    when they are blocked from placing a new request."""
    if client is None:
        return True, ""
    if getattr(client, "is_overdue", False):
        return False, "برجاء سداد المبلغ المتأخر لإكمال الطلب"
    return True, ""
