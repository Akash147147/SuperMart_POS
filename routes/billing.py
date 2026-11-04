"""Billing counter routes - barcode scanning, cart, and invoice creation."""
import json
from functools import wraps
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from models import db, Product, Store, Customer, HeldBill
from services.billing_service import (
    lookup_product_by_barcode,
    search_products,
    calculate_cart_totals,
    complete_sale,
)

billing_bp = Blueprint('billing', __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@billing_bp.route('/billing')
@login_required
def billing_page():
    """Render the cashier billing counter."""
    store = Store.query.get(current_user.store_id)
    return render_template('billing.html', store=store)


# ---------------------------------------------------------------------------
# Barcode scan / product lookup
# ---------------------------------------------------------------------------

@billing_bp.route('/api/billing/scan', methods=['POST'])
@login_required
def scan_barcode():
    """Look up a product by barcode in the current user's store."""
    data = request.get_json(silent=True) or {}
    barcode = (data.get('barcode') or '').strip()

    if not barcode:
        return jsonify({'success': False, 'message': 'Barcode is required'}), 400

    product = lookup_product_by_barcode(barcode, current_user.store_id)
    if not product:
        return jsonify({'success': False, 'message': f'Product not found for barcode: {barcode}'}), 404

    return jsonify({'success': True, 'data': product.to_dict()})


# ---------------------------------------------------------------------------
# Product search
# ---------------------------------------------------------------------------

@billing_bp.route('/api/billing/search', methods=['POST'])
@login_required
def search():
    """Search products by name, barcode, or HSN code."""
    data = request.get_json(silent=True) or {}
    query = (data.get('query') or '').strip()

    if not query:
        return jsonify({'success': False, 'message': 'Search query is required'}), 400

    results = search_products(query, current_user.store_id)
    return jsonify({'success': True, 'data': results})


# ---------------------------------------------------------------------------
# Cart calculation
# ---------------------------------------------------------------------------

@billing_bp.route('/api/billing/calculate', methods=['POST'])
@login_required
def calculate():
    """Calculate cart totals including taxes, discounts, and round-off."""
    data = request.get_json(silent=True) or {}
    cart_items = data.get('cart_items', [])

    if not cart_items:
        return jsonify({'success': False, 'message': 'Cart is empty'}), 400

    store = Store.query.get(current_user.store_id)
    if not store:
        return jsonify({'success': False, 'message': 'Store not found'}), 404

    try:
        totals = calculate_cart_totals(cart_items, store)
        return jsonify({'success': True, 'data': totals})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# Complete sale
# ---------------------------------------------------------------------------

@billing_bp.route('/api/billing/complete', methods=['POST'])
@login_required
def complete():
    """Complete a sale transaction – create invoice, deduct stock, record payment."""
    data = request.get_json(silent=True) or {}

    cart_items = data.get('cart_items', [])
    payment_data = data.get('payment_data', [])
    customer_id = data.get('customer_id')
    bill_discount_pct = Decimal(str(data.get('bill_discount_pct', 0)))
    bill_discount_amt = Decimal(str(data.get('bill_discount_amt', 0)))
    notes = data.get('notes', '')

    # --- Validations ---
    if not cart_items:
        return jsonify({'success': False, 'message': 'Cart is empty'}), 400

    if not payment_data:
        return jsonify({'success': False, 'message': 'Payment information is required'}), 400

    store = Store.query.get(current_user.store_id)
    if not store:
        return jsonify({'success': False, 'message': 'Store not found'}), 404

    try:
        invoice = complete_sale(
            cart_items=cart_items,
            payment_data=payment_data,
            store=store,
            cashier=current_user,
            counter=None,
            customer_id=customer_id,
            bill_discount_pct=bill_discount_pct,
            bill_discount_amt=bill_discount_amt,
            notes=notes,
        )

        return jsonify({
            'success': True,
            'message': 'Sale completed successfully',
            'data': invoice.to_dict(),
        })

    except (ValueError, InvalidOperation) as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'An error occurred: {str(e)}'}), 500


# ---------------------------------------------------------------------------
# Hold / Resume / Discard bills
# ---------------------------------------------------------------------------

@billing_bp.route('/api/billing/hold', methods=['POST'])
@login_required
def hold_bill():
    """Hold the current bill for later resumption."""
    data = request.get_json(silent=True) or {}
    cart_items = data.get('cart_items', [])
    customer_id = data.get('customer_id')
    bill_notes = data.get('notes', '')

    if not cart_items:
        return jsonify({'success': False, 'message': 'Cart is empty – nothing to hold'}), 400

    held = HeldBill(
        store_id=current_user.store_id,
        cashier_id=current_user.id,
        customer_id=customer_id,
        bill_data=cart_items,
        notes=bill_notes,
    )
    db.session.add(held)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Bill held successfully',
        'data': {'held_bill_id': held.id},
    })


@billing_bp.route('/api/billing/held', methods=['GET'])
@login_required
def list_held_bills():
    """List all held bills for the current user's store."""
    held_bills = HeldBill.query.filter_by(
        store_id=current_user.store_id,
    ).order_by(HeldBill.created_at.desc()).all()

    result = []
    for hb in held_bills:
        result.append({
            'id': hb.id,
            'cashier_name': hb.cashier.full_name if hb.cashier else '',
            'customer_name': hb.customer.name if hb.customer else '',
            'items_count': len(hb.bill_data) if hb.bill_data else 0,
            'notes': hb.notes or '',
            'created_at': hb.created_at.isoformat() if hb.created_at else '',
        })

    return jsonify({'success': True, 'data': result})


@billing_bp.route('/api/billing/resume/<int:held_bill_id>', methods=['POST'])
@login_required
def resume_held_bill(held_bill_id):
    """Resume a held bill – return cart data and delete the held record."""
    held = HeldBill.query.filter_by(
        id=held_bill_id,
        store_id=current_user.store_id,
    ).first()

    if not held:
        return jsonify({'success': False, 'message': 'Held bill not found'}), 404

    cart_data = held.bill_data
    customer_id = held.customer_id
    notes = held.notes

    db.session.delete(held)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Bill resumed',
        'data': {
            'cart_items': cart_data,
            'customer_id': customer_id,
            'notes': notes or '',
        },
    })


@billing_bp.route('/api/billing/held/<int:held_bill_id>', methods=['DELETE'])
@login_required
def discard_held_bill(held_bill_id):
    """Discard (permanently delete) a held bill."""
    held = HeldBill.query.filter_by(
        id=held_bill_id,
        store_id=current_user.store_id,
    ).first()

    if not held:
        return jsonify({'success': False, 'message': 'Held bill not found'}), 404

    db.session.delete(held)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Held bill discarded'})
