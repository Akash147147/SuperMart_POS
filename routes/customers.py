"""Customer management routes."""
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_

from models import db, Customer, AuditLog

customers_bp = Blueprint('customers', __name__)


def _log_audit(action, entity_type=None, entity_id=None, details=None):
    """Create an audit log entry."""
    log = AuditLog(
        store_id=current_user.store_id,
        user_id=current_user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=request.remote_addr,
    )
    db.session.add(log)


# ---------------------------------------------------------------------------
# List / Search customers
# ---------------------------------------------------------------------------

@customers_bp.route('/api/customers', methods=['GET'])
@login_required
def list_customers():
    """List or search customers for the current store.

    Query params:
        q       – search by name or phone (partial match)
        page    – page number (default 1)
        per_page – items per page (default 20)
    """
    try:
        store_id = current_user.store_id
        q = request.args.get('q', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        query = Customer.query.filter_by(store_id=store_id, is_active=True)

        if q:
            search = f'%{q}%'
            query = query.filter(
                or_(
                    Customer.name.ilike(search),
                    Customer.phone.ilike(search),
                    Customer.email.ilike(search),
                )
            )

        query = query.order_by(Customer.name)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        data = [c.to_dict() for c in pagination.items]

        return jsonify({
            'success': True,
            'data': data,
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages,
            },
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# Search customers (quick-add during billing)
# ---------------------------------------------------------------------------

@customers_bp.route('/api/customers/search', methods=['GET'])
@login_required
def search_customers():
    """Quick search by phone or name – returns up to 10 results for billing."""
    try:
        store_id = current_user.store_id
        q = request.args.get('q', '').strip()

        if not q or len(q) < 2:
            return jsonify({'success': True, 'data': []})

        search = f'%{q}%'
        customers = Customer.query.filter(
            Customer.store_id == store_id,
            Customer.is_active == True,
            or_(
                Customer.name.ilike(search),
                Customer.phone.ilike(search),
            ),
        ).order_by(Customer.name).limit(10).all()

        data = [c.to_dict() for c in customers]
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# Get single customer
# ---------------------------------------------------------------------------

@customers_bp.route('/api/customers/<int:customer_id>', methods=['GET'])
@login_required
def get_customer(customer_id):
    """Return a single customer's details."""
    try:
        customer = Customer.query.get(customer_id)
        if not customer or customer.store_id != current_user.store_id:
            return jsonify({'success': False, 'message': 'Customer not found'}), 404

        # Include purchase history summary
        total_invoices = customer.invoices.filter_by(status='completed').count()
        total_spent = sum(
            float(inv.final_amount) for inv in customer.invoices.filter_by(status='completed').all()
        )

        data = customer.to_dict()
        data['total_invoices'] = total_invoices
        data['total_spent'] = total_spent

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# Create customer
# ---------------------------------------------------------------------------

@customers_bp.route('/api/customers', methods=['POST'])
@login_required
def create_customer():
    """Create a new customer."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        if not data.get('name'):
            return jsonify({'success': False, 'message': 'Customer name is required'}), 400

        # Check for duplicate phone in the same store
        if data.get('phone'):
            existing = Customer.query.filter_by(
                store_id=current_user.store_id,
                phone=data['phone'],
                is_active=True,
            ).first()
            if existing:
                return jsonify({
                    'success': False,
                    'message': 'A customer with this phone number already exists',
                    'data': existing.to_dict(),
                }), 400

        customer = Customer(
            store_id=current_user.store_id,
            name=data['name'],
            phone=data.get('phone'),
            email=data.get('email'),
            address=data.get('address'),
            gstin=data.get('gstin'),
            is_active=True,
        )
        db.session.add(customer)
        db.session.flush()

        _log_audit('create_customer', 'customer', customer.id, {'name': customer.name})
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Customer created successfully',
            'data': customer.to_dict(),
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# Update customer
# ---------------------------------------------------------------------------

@customers_bp.route('/api/customers/<int:customer_id>', methods=['PUT'])
@login_required
def update_customer(customer_id):
    """Update an existing customer."""
    try:
        customer = Customer.query.get(customer_id)
        if not customer or customer.store_id != current_user.store_id:
            return jsonify({'success': False, 'message': 'Customer not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        # Check for duplicate phone if phone is being changed
        if 'phone' in data and data['phone'] and data['phone'] != customer.phone:
            existing = Customer.query.filter(
                Customer.store_id == current_user.store_id,
                Customer.phone == data['phone'],
                Customer.is_active == True,
                Customer.id != customer_id,
            ).first()
            if existing:
                return jsonify({
                    'success': False,
                    'message': 'A customer with this phone number already exists',
                }), 400

        updatable = ['name', 'phone', 'email', 'address', 'gstin']
        for field in updatable:
            if field in data:
                setattr(customer, field, data[field])

        _log_audit('update_customer', 'customer', customer.id, {'fields': list(data.keys())})
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Customer updated successfully',
            'data': customer.to_dict(),
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
