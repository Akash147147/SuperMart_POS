"""Authentication routes."""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from models import db, User, Role, Store, Product, Category, Invoice, InvoiceItem, Payment, AuditLog, StockMovement

auth_bp = Blueprint('auth', __name__)


def admin_required(f):
    """Decorator that checks the current user has admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
        if not current_user.is_admin:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Admin access required'}), 403
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('dashboard.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and authentication."""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please enter both username and password.', 'warning')
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash('Invalid username or password.', 'danger')
            # Log failed attempt
            audit = AuditLog(
                action='login_failed',
                entity_type='user',
                details={'username': username, 'reason': 'invalid_credentials'},
                ip_address=request.remote_addr,
            )
            db.session.add(audit)
            db.session.commit()
            return render_template('login.html')

        if not user.is_active:
            flash('Your account has been deactivated. Contact admin.', 'danger')
            return render_template('login.html')

        # Successful login
        login_user(user, remember=request.form.get('remember', False))

        # Update last_login timestamp
        user.last_login = datetime.now(timezone.utc)
        db.session.commit()

        # Store store_id in session for easy access
        session['store_id'] = user.store_id

        # Create audit log for successful login
        audit = AuditLog(
            store_id=user.store_id,
            user_id=user.id,
            action='login',
            entity_type='user',
            entity_id=user.id,
            details={'full_name': user.full_name, 'role': user.role.name if user.role else ''},
            ip_address=request.remote_addr,
        )
        db.session.add(audit)
        db.session.commit()

        flash(f'Welcome back, {user.full_name}!', 'success')

        # Redirect to the page the user was trying to access, or dashboard
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('dashboard.dashboard'))

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Log out the current user."""
    # Create audit log before logging out
    audit = AuditLog(
        store_id=current_user.store_id,
        user_id=current_user.id,
        action='logout',
        entity_type='user',
        entity_id=current_user.id,
        details={'full_name': current_user.full_name},
        ip_address=request.remote_addr,
    )
    db.session.add(audit)
    db.session.commit()

    logout_user()
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
