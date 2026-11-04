"""Inventory routes and management."""
from decimal import Decimal
from functools import wraps
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from models.base import db
from models.product import Product
from services.inventory_service import (
    stock_in, stock_adjustment, record_damaged,
    get_stock_movements, get_low_stock_products, get_out_of_stock_products
)

inventory_bp = Blueprint('inventory', __name__)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({'success': False, 'message': 'Admin privilege required'}), 403
        return f(*args, **kwargs)
    return decorated_function


@inventory_bp.route('/inventory')
@login_required
@admin_required
def inventory_page():
    return render_template('inventory.html')


@inventory_bp.route('/api/inventory/products', methods=['GET'])
@login_required
def list_inventory():
    store_id = current_user.store_id or 1
    products = Product.query.filter_by(store_id=store_id, is_active=True).all()
    return jsonify({
        'success': True,
        'products': [p.to_dict() for p in products]
    })


@inventory_bp.route('/api/inventory/stock-in', methods=['POST'])
@login_required
@admin_required
def add_stock():
    data = request.get_json() or {}
    product_id = data.get('product_id')
    quantity = data.get('quantity')
    notes = data.get('notes', '')
    if not product_id or not quantity:
        return jsonify({'success': False, 'message': 'Product ID and quantity required'}), 400

    try:
        p = stock_in(
            product_id=product_id,
            quantity=quantity,
            store_id=current_user.store_id or 1,
            user_id=current_user.id,
            notes=notes
        )
        return jsonify({'success': True, 'product': p.to_dict(), 'message': 'Stock added successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@inventory_bp.route('/api/inventory/adjust', methods=['POST'])
@login_required
@admin_required
def adjust_stock():
    data = request.get_json() or {}
    product_id = data.get('product_id')
    new_quantity = data.get('new_quantity')
    reason = data.get('reason', '')
    if not product_id or new_quantity is None:
        return jsonify({'success': False, 'message': 'Product ID and new quantity required'}), 400

    try:
        p = stock_adjustment(
            product_id=product_id,
            new_quantity=new_quantity,
            store_id=current_user.store_id or 1,
            user_id=current_user.id,
            reason=reason
        )
        return jsonify({'success': True, 'product': p.to_dict(), 'message': 'Stock adjusted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@inventory_bp.route('/api/inventory/damaged', methods=['POST'])
@login_required
@admin_required
def damage_stock():
    data = request.get_json() or {}
    product_id = data.get('product_id')
    quantity = data.get('quantity')
    notes = data.get('notes', '')
    if not product_id or not quantity:
        return jsonify({'success': False, 'message': 'Product ID and quantity required'}), 400

    try:
        p = record_damaged(
            product_id=product_id,
            quantity=quantity,
            store_id=current_user.store_id or 1,
            user_id=current_user.id,
            notes=notes
        )
        return jsonify({'success': True, 'product': p.to_dict(), 'message': 'Damaged stock recorded'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@inventory_bp.route('/api/inventory/movements', methods=['GET'])
@login_required
def movements():
    store_id = current_user.store_id or 1
    product_id = request.args.get('product_id', type=int)
    m_type = request.args.get('type')
    history = get_stock_movements(product_id=product_id, store_id=store_id, movement_type=m_type)
    return jsonify({
        'success': True,
        'movements': [{
            'id': m.id,
            'product_name': m.product.name if m.product else 'N/A',
            'type': m.movement_type,
            'quantity_change': str(m.quantity_change),
            'quantity_before': str(m.quantity_before),
            'quantity_after': str(m.quantity_after),
            'notes': m.notes or '',
            'created_at': m.created_at.strftime('%Y-%m-%d %H:%M:%S') if m.created_at else ''
        } for m in history]
    })


@inventory_bp.route('/api/inventory/low-stock', methods=['GET'])
@login_required
def low_stock():
    store_id = current_user.store_id or 1
    prods = get_low_stock_products(store_id)
    return jsonify({'success': True, 'products': [p.to_dict() for p in prods]})


@inventory_bp.route('/api/inventory/out-of-stock', methods=['GET'])
@login_required
def out_of_stock():
    store_id = current_user.store_id or 1
    prods = get_out_of_stock_products(store_id)
    return jsonify({'success': True, 'products': [p.to_dict() for p in prods]})

