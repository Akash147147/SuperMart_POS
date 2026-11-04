"""Settings routes - store config, user management, and billing counters."""
import os
from functools import wraps
from flask import Blueprint, request, jsonify, render_template, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models.base import db
from models.store import Store, BillingCounter
from models.user import User, Role
from models.audit import AuditLog

settings_bp = Blueprint('settings', __name__)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'}


def admin_required(f):
    """Restrict access to admin users only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def _allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


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
# Page route
# ---------------------------------------------------------------------------

@settings_bp.route('/settings')
@login_required
@admin_required
def settings_page():
    """Render the settings dashboard."""
    return render_template('settings.html')


# =========================================================================
# Store Settings
# =========================================================================

@settings_bp.route('/api/settings/store', methods=['GET'])
@login_required
@admin_required
def get_store():
    """Return current store details."""
    try:
        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        data = {
            'id': store.id,
            'name': store.name,
            'address': store.address or '',
            'city': store.city or '',
            'state': store.state or '',
            'state_code': store.state_code or '',
            'pincode': store.pincode or '',
            'phone': store.phone or '',
            'email': store.email or '',
            'gstin': store.gstin or '',
            'logo_path': store.logo_path or '',
            'invoice_prefix': store.invoice_prefix or 'INV',
            'currency': store.currency or 'INR',
            'tax_type': store.tax_type or 'intra-state',
            'receipt_footer': store.receipt_footer or '',
            'receipt_paper_width': store.receipt_paper_width or '80mm',
        }

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@settings_bp.route('/api/settings/store', methods=['PUT'])
@login_required
@admin_required
def update_store():
    """Update store details."""
    try:
        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        # Updatable fields
        updatable = [
            'name', 'address', 'city', 'state', 'state_code', 'pincode',
            'phone', 'email', 'gstin', 'invoice_prefix', 'currency',
            'tax_type', 'receipt_footer', 'receipt_paper_width',
        ]
        for field in updatable:
            if field in data:
                setattr(store, field, data[field])

        _log_audit('update_store', 'store', store.id, {'fields': list(data.keys())})
        db.session.commit()

        return jsonify({'success': True, 'message': 'Store settings updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@settings_bp.route('/api/settings/store/logo', methods=['POST'])
@login_required
@admin_required
def upload_logo():
    """Upload a store logo image."""
    try:
        if 'logo' not in request.files:
            return jsonify({'success': False, 'message': 'No logo file provided'}), 400

        file = request.files['logo']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400

        if not _allowed_image(file.filename):
            return jsonify({
                'success': False,
                'message': f'Invalid file type. Allowed: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}',
            }), 400

        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        filename = secure_filename(f"logo_{store.id}_{file.filename}")
        images_dir = os.path.join(current_app.root_path, 'static', 'images')
        os.makedirs(images_dir, exist_ok=True)
        filepath = os.path.join(images_dir, filename)
        file.save(filepath)

        store.logo_path = f'static/images/{filename}'
        _log_audit('upload_logo', 'store', store.id)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Logo uploaded successfully',
            'data': {'logo_path': store.logo_path},
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# =========================================================================
# User Management
# =========================================================================

@settings_bp.route('/api/settings/users', methods=['GET'])
@login_required
@admin_required
def list_users():
    """List all users for the current store."""
    try:
        users = User.query.filter_by(store_id=current_user.store_id).order_by(User.full_name).all()

        data = [
            {
                'id': u.id,
                'username': u.username,
                'full_name': u.full_name,
                'email': u.email or '',
                'phone': u.phone or '',
                'role_id': u.role_id,
                'role_name': u.role.name if u.role else '',
                'is_active': u.is_active,
                'last_login': u.last_login.isoformat() if u.last_login else None,
                'created_at': u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ]

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@settings_bp.route('/api/settings/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    """Create a new user."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        # Validate required fields
        required = ['username', 'password', 'full_name', 'role_id']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({
                'success': False,
                'message': f'Missing required fields: {", ".join(missing)}',
            }), 400

        # Check for duplicate username
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'success': False, 'message': 'Username already exists'}), 400

        # Verify role exists
        role = Role.query.get(data['role_id'])
        if not role:
            return jsonify({'success': False, 'message': 'Invalid role'}), 400

        user = User(
            username=data['username'],
            full_name=data['full_name'],
            email=data.get('email'),
            phone=data.get('phone'),
            role_id=data['role_id'],
            store_id=data.get('store_id', current_user.store_id),
            is_active=True,
        )
        user.set_password(data['password'])

        db.session.add(user)
        _log_audit('create_user', 'user', None, {'username': user.username})
        db.session.flush()  # get user.id for audit
        _log_audit('create_user', 'user', user.id, {'username': user.username})
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'User created successfully',
            'data': {'id': user.id, 'username': user.username},
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@settings_bp.route('/api/settings/users/<int:user_id>', methods=['PUT'])
@login_required
@admin_required
def update_user(user_id):
    """Update an existing user."""
    try:
        user = User.query.get(user_id)
        if not user or user.store_id != current_user.store_id:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        if 'full_name' in data:
            user.full_name = data['full_name']
        if 'email' in data:
            user.email = data['email']
        if 'phone' in data:
            user.phone = data['phone']
        if 'role_id' in data:
            role = Role.query.get(data['role_id'])
            if not role:
                return jsonify({'success': False, 'message': 'Invalid role'}), 400
            user.role_id = data['role_id']
        if 'is_active' in data:
            user.is_active = data['is_active']
        if 'password' in data and data['password']:
            user.set_password(data['password'])

        _log_audit('update_user', 'user', user.id, {'fields': list(data.keys())})
        db.session.commit()

        return jsonify({'success': True, 'message': 'User updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@settings_bp.route('/api/settings/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def deactivate_user(user_id):
    """Soft-delete (deactivate) a user."""
    try:
        user = User.query.get(user_id)
        if not user or user.store_id != current_user.store_id:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        if user.id == current_user.id:
            return jsonify({'success': False, 'message': 'Cannot deactivate yourself'}), 400

        user.is_active = False
        _log_audit('deactivate_user', 'user', user.id, {'username': user.username})
        db.session.commit()

        return jsonify({'success': True, 'message': 'User deactivated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# =========================================================================
# Billing Counters
# =========================================================================

@settings_bp.route('/api/settings/counters', methods=['GET'])
@login_required
def list_counters():
    """List all billing counters for the current store."""
    try:
        counters = BillingCounter.query.filter_by(
            store_id=current_user.store_id,
        ).order_by(BillingCounter.name).all()

        data = [
            {
                'id': c.id,
                'name': c.name,
                'is_active': c.is_active,
                'created_at': c.created_at.isoformat() if c.created_at else None,
            }
            for c in counters
        ]

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@settings_bp.route('/api/settings/counters', methods=['POST'])
@login_required
@admin_required
def create_counter():
    """Create a new billing counter."""
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'success': False, 'message': 'Counter name is required'}), 400

        counter = BillingCounter(
            store_id=current_user.store_id,
            name=data['name'],
            is_active=data.get('is_active', True),
        )
        db.session.add(counter)
        _log_audit('create_counter', 'counter', None, {'name': counter.name})
        db.session.flush()
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Counter created successfully',
            'data': {'id': counter.id, 'name': counter.name},
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@settings_bp.route('/api/settings/counters/<int:counter_id>', methods=['PUT'])
@login_required
def update_counter(counter_id):
    """Update a billing counter."""
    try:
        counter = BillingCounter.query.get(counter_id)
        if not counter or counter.store_id != current_user.store_id:
            return jsonify({'success': False, 'message': 'Counter not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        if 'name' in data:
            counter.name = data['name']
        if 'is_active' in data:
            counter.is_active = data['is_active']

        _log_audit('update_counter', 'counter', counter.id, {'fields': list(data.keys())})
        db.session.commit()

        return jsonify({'success': True, 'message': 'Counter updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@settings_bp.route('/api/settings/counters/<int:counter_id>', methods=['DELETE'])
@login_required
@admin_required
def deactivate_counter(counter_id):
    """Soft-delete (deactivate) a billing counter."""
    try:
        counter = BillingCounter.query.get(counter_id)
        if not counter or counter.store_id != current_user.store_id:
            return jsonify({'success': False, 'message': 'Counter not found'}), 404

        counter.is_active = False
        _log_audit('deactivate_counter', 'counter', counter.id, {'name': counter.name})
        db.session.commit()

        return jsonify({'success': True, 'message': 'Counter deactivated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
