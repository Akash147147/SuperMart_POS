"""Dashboard routes."""
from flask import Blueprint, jsonify, render_template
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import func
from models.base import db
from models.product import Product
from models.invoice import Invoice, InvoiceItem

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard page."""
    return render_template('dashboard.html')


@dashboard_bp.route('/api/dashboard/stats')
@login_required
def dashboard_stats():
    """Return dashboard statistics as JSON for the current user's store."""
    store_id = current_user.store_id
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)

    # ---------- Today's Sales ----------
    today_sales_result = db.session.query(
        func.coalesce(func.sum(Invoice.final_amount), 0),
        func.coalesce(func.count(Invoice.id), 0),
        func.coalesce(func.sum(Invoice.total_quantity), 0),
    ).filter(
        Invoice.store_id == store_id,
        Invoice.status == 'completed',
        Invoice.invoice_date >= today_start,
        Invoice.invoice_date < today_end,
    ).first()

    today_sales = float(today_sales_result[0]) if today_sales_result[0] else 0.0
    today_bills = int(today_sales_result[1]) if today_sales_result[1] else 0
    today_products_sold = float(today_sales_result[2]) if today_sales_result[2] else 0.0

    # ---------- Low Stock Count ----------
    low_stock_count = Product.query.filter(
        Product.store_id == store_id,
        Product.is_active == True,
        Product.stock_quantity <= Product.min_stock_level,
    ).count()

    # ---------- Top 5 Products This Month ----------
    month_start = date.today().replace(day=1)
    month_start_dt = datetime.combine(month_start, datetime.min.time()).replace(tzinfo=timezone.utc)

    top_products_query = db.session.query(
        InvoiceItem.product_name,
        func.sum(InvoiceItem.quantity).label('total_qty'),
        func.sum(InvoiceItem.total_amount).label('total_revenue'),
    ).join(
        Invoice, InvoiceItem.invoice_id == Invoice.id,
    ).filter(
        Invoice.store_id == store_id,
        Invoice.status == 'completed',
        Invoice.invoice_date >= month_start_dt,
    ).group_by(
        InvoiceItem.product_name,
    ).order_by(
        func.sum(InvoiceItem.quantity).desc(),
    ).limit(5).all()

    top_products = [
        {
            'name': row.product_name,
            'quantity': float(row.total_qty),
            'revenue': float(row.total_revenue),
        }
        for row in top_products_query
    ]

    # ---------- Recent 10 Transactions ----------
    recent_invoices = Invoice.query.filter(
        Invoice.store_id == store_id,
    ).order_by(
        Invoice.invoice_date.desc(),
    ).limit(10).all()

    recent_transactions = [
        {
            'id': inv.id,
            'invoice_number': inv.invoice_number,
            'cashier_name': inv.cashier.full_name if inv.cashier else '',
            'total_items': inv.total_items,
            'final_amount': str(inv.final_amount),
            'status': inv.status,
            'payment_method': inv.payments[0].payment_method if inv.payments else '',
            'invoice_date': inv.invoice_date.isoformat() if inv.invoice_date else '',
        }
        for inv in recent_invoices
    ]

    # ---------- Daily Sales Chart (Last 7 Days) ----------
    daily_sales_chart = _get_daily_sales(store_id, days=7)
    daily_sales_list = [
        {'date': label, 'total': val, 'count': cnt}
        for label, val, cnt in zip(daily_sales_chart['labels'], daily_sales_chart['values'], daily_sales_chart['counts'])
    ]

    # ---------- Monthly Sales Chart (Last 6 Months) ----------
    monthly_sales_chart = _get_monthly_sales(store_id, months=6)
    monthly_sales_list = [
        {'month': label, 'total': val, 'count': cnt}
        for label, val, cnt in zip(monthly_sales_chart['labels'], monthly_sales_chart['values'], monthly_sales_chart['counts'])
    ]

    return jsonify({
        'success': True,
        'today_sales': today_sales,
        'today_bills': today_bills,
        'bills_generated': today_bills,
        'today_products_sold': today_products_sold,
        'products_sold': today_products_sold,
        'low_stock_count': low_stock_count,
        'top_products': top_products,
        'recent_transactions': recent_transactions,
        'daily_sales': daily_sales_list,
        'monthly_sales': monthly_sales_list,
        'daily_sales_chart': daily_sales_chart,
        'monthly_sales_chart': monthly_sales_chart,
        'data': {
            'today_sales': today_sales,
            'today_bills': today_bills,
            'bills_generated': today_bills,
            'today_products_sold': today_products_sold,
            'products_sold': today_products_sold,
            'low_stock_count': low_stock_count,
            'top_products': top_products,
            'recent_transactions': recent_transactions,
            'daily_sales': daily_sales_list,
            'monthly_sales': monthly_sales_list,
            'daily_sales_chart': daily_sales_chart,
            'monthly_sales_chart': monthly_sales_chart,
        },
    })


def _get_daily_sales(store_id, days=7):
    """Get daily sales totals for the last N days."""
    labels = []
    values = []
    counts = []

    for i in range(days - 1, -1, -1):
        target_date = date.today() - timedelta(days=i)
        day_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        result = db.session.query(
            func.coalesce(func.sum(Invoice.final_amount), 0),
            func.coalesce(func.count(Invoice.id), 0),
        ).filter(
            Invoice.store_id == store_id,
            Invoice.status == 'completed',
            Invoice.invoice_date >= day_start,
            Invoice.invoice_date < day_end,
        ).first()

        labels.append(target_date.strftime('%d %b'))
        values.append(float(result[0]))
        counts.append(int(result[1]))

    return {
        'labels': labels,
        'values': values,
        'counts': counts,
    }


def _get_monthly_sales(store_id, months=6):
    """Get monthly sales totals for the last N months."""
    labels = []
    values = []
    counts = []

    today = date.today()

    for i in range(months - 1, -1, -1):
        # Calculate month offset
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1

        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1)
        else:
            month_end = date(year, month + 1, 1)

        month_start_dt = datetime.combine(month_start, datetime.min.time()).replace(tzinfo=timezone.utc)
        month_end_dt = datetime.combine(month_end, datetime.min.time()).replace(tzinfo=timezone.utc)

        result = db.session.query(
            func.coalesce(func.sum(Invoice.final_amount), 0),
            func.coalesce(func.count(Invoice.id), 0),
        ).filter(
            Invoice.store_id == store_id,
            Invoice.status == 'completed',
            Invoice.invoice_date >= month_start_dt,
            Invoice.invoice_date < month_end_dt,
        ).first()

        labels.append(month_start.strftime('%b %Y'))
        values.append(float(result[0]))
        counts.append(int(result[1]))

    return {
        'labels': labels,
        'values': values,
        'counts': counts,
    }
