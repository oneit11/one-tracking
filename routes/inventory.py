from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import desc, or_
from models import db
from models.extras import SparePart, StockMovement
from utils.decorators import admin_required
from services.audit import log_action

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.route("/")
@admin_required
def parts_list():
    q = request.args.get("q", "").strip()
    query = SparePart.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(SparePart.name.ilike(like),
                                 SparePart.sku.ilike(like),
                                 SparePart.category.ilike(like)))
    parts = query.order_by(SparePart.name).all()

    low_stock = [p for p in parts if p.quantity is not None and p.min_quantity is not None
                 and float(p.quantity) <= float(p.min_quantity)]

    return render_template("admin/inventory/parts_list.html",
                           parts=parts, low_stock=low_stock, q=q)


@inventory_bp.route("/parts/new", methods=["GET", "POST"])
@admin_required
def part_new():
    if request.method == "POST":
        p = SparePart(
            sku=request.form.get("sku", "").strip(),
            name=request.form.get("name", "").strip(),
            category=request.form.get("category", "").strip(),
            unit=request.form.get("unit", "قطعة").strip(),
            quantity=float(request.form.get("quantity") or 0),
            min_quantity=float(request.form.get("min_quantity") or 0),
            unit_price=float(request.form.get("unit_price") or 0),
            location=request.form.get("location", "").strip(),
            notes=request.form.get("notes", "").strip(),
        )
        db.session.add(p)
        db.session.commit()
        log_action("inventory.part_created", entity_type="part", entity_id=p.id)
        flash(f"تم إضافة {p.name}", "success")
        return redirect(url_for("inventory.parts_list"))
    return render_template("admin/inventory/part_form.html", part=None)


@inventory_bp.route("/parts/<int:pid>", methods=["GET", "POST"])
@admin_required
def part_edit(pid):
    p = SparePart.query.get_or_404(pid)
    if request.method == "POST":
        p.sku = request.form.get("sku", "").strip()
        p.name = request.form.get("name", "").strip()
        p.category = request.form.get("category", "").strip()
        p.unit = request.form.get("unit", p.unit).strip()
        p.min_quantity = float(request.form.get("min_quantity") or 0)
        p.unit_price = float(request.form.get("unit_price") or 0)
        p.location = request.form.get("location", "").strip()
        p.notes = request.form.get("notes", "").strip()
        p.active = bool(request.form.get("active"))
        db.session.commit()
        log_action("inventory.part_updated", entity_type="part", entity_id=p.id)
        flash("تم الحفظ", "success")
        return redirect(url_for("inventory.parts_list"))
    return render_template("admin/inventory/part_form.html", part=p)


@inventory_bp.route("/parts/<int:pid>/movement", methods=["POST"])
@admin_required
def add_movement(pid):
    p = SparePart.query.get_or_404(pid)
    kind = request.form.get("kind", "out")
    qty = float(request.form.get("quantity") or 0)
    if qty <= 0:
        flash("الكمية يجب أن تكون أكبر من صفر", "danger")
        return redirect(url_for("inventory.part_edit", pid=pid))

    m = StockMovement(
        part_id=p.id, kind=kind, quantity=qty,
        unit_price=float(request.form.get("unit_price") or p.unit_price or 0),
        reference=request.form.get("reference", "").strip(),
        notes=request.form.get("notes", "").strip(),
        user_id=current_user.id,
    )
    db.session.add(m)

    # Update stock
    if kind == "in":
        p.quantity = float(p.quantity or 0) + qty
    elif kind == "out":
        p.quantity = max(0, float(p.quantity or 0) - qty)
    else:  # adjust
        p.quantity = qty

    db.session.commit()
    log_action("inventory.movement", entity_type="part", entity_id=p.id, details=f"{kind} {qty}")
    flash("تم تسجيل الحركة", "success")
    return redirect(url_for("inventory.part_edit", pid=pid))


@inventory_bp.route("/movements")
@admin_required
def movements():
    movs = StockMovement.query.order_by(desc(StockMovement.created_at)).limit(200).all()
    return render_template("admin/inventory/movements.html", movements=movs)
