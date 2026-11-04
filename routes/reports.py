"""Reports routes - sales, GST, inventory, and analytics reports."""
from functools import wraps
from datetime import datetime, date
from decimal import Decimal

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from sqlalchemy import func, cast, Date

from models.base import db
from models.store import Store
from models.product import Product, Category
from models.invoice import Invoice, InvoiceItem, InvoiceTax
from models.payment import Payment
from services.inventory_service import get_low_stock_products

reports_bp = Blueprint('reports', __name__)


def admin_required(f):
    """Restrict access to admin users only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date_range():
    """Parse start_date / end_date query params, defaulting to current month."""
    today = date.today()
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    if start_str:
        try:
            start = datetime.strptime(start_str, '%Y-%m-%d').date()
        except ValueError:
            start = today.replace(day=1)
    else:
        start = today.replace(day=1)

    if end_str:
        try:
            end = datetime.strptime(end_str, '%Y-%m-%d').date()
        except ValueError:
            end = today
    else:
        end = today

    # Convert to datetime range (start of day → end of day)
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    return start, end, start_dt, end_dt


def _completed_invoices_query(store_id, start_dt, end_dt):
    """Base query for completed invoices within the date range."""
    return Invoice.query.filter(
        Invoice.store_id == store_id,
        Invoice.status == 'completed',
        Invoice.invoice_date >= start_dt,
        Invoice.invoice_date <= end_dt,
    )


# ---------------------------------------------------------------------------
# Page route
# ---------------------------------------------------------------------------

@reports_bp.route('/reports')
@login_required
@admin_required
def reports_page():
    """Render the reports dashboard."""
    return render_template('reports.html')


# ---------------------------------------------------------------------------
# API: Sales Summary
# ---------------------------------------------------------------------------

@reports_bp.route('/api/reports/sales-summary')
@login_required
@admin_required
def sales_summary():
    """Aggregated sales summary for the date range."""
    try:
        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        start, end, start_dt, end_dt = _parse_date_range()

        result = db.session.query(
            func.coalesce(func.sum(Invoice.final_amount), 0).label('total_sales'),
            func.count(Invoice.id).label('total_bills'),
            func.coalesce(func.sum(Invoice.total_items), 0).label('total_items'),
            func.coalesce(func.sum(Invoice.tax_total), 0).label('total_tax'),
        ).filter(
            Invoice.store_id == store.id,
            Invoice.status == 'completed',
            Invoice.invoice_date >= start_dt,
            Invoice.invoice_date <= end_dt,
        ).first()

        total_sales = float(result.total_sales or 0)
        total_bills = int(result.total_bills or 0)
        total_items = int(result.total_items or 0)
        total_tax = float(result.total_tax or 0)
        average_bill_value = round(total_sales / total_bills, 2) if total_bills else 0.0

        return jsonify({
            'success': True,
            'data': {
                'total_sales': total_sales,
                'total_bills': total_bills,
                'total_items': total_items,
                'total_tax': total_tax,
                'average_bill_value': average_bill_value,
                'start_date': start.isoformat(),
                'end_date': end.isoformat(),
            },
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# API: Daily Sales (chart data)
# ---------------------------------------------------------------------------

@reports_bp.route('/api/reports/daily-sales')
@login_required
@admin_required
def daily_sales():
    """Daily sales totals for the date range – ideal for chart rendering."""
    try:
        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        start, end, start_dt, end_dt = _parse_date_range()

        rows = db.session.query(
            cast(Invoice.invoice_date, Date).label('sale_date'),
            func.coalesce(func.sum(Invoice.final_amount), 0).label('total_sales'),
            func.count(Invoice.id).label('bill_count'),
        ).filter(
            Invoice.store_id == store.id,
            Invoice.status == 'completed',
            Invoice.invoice_date >= start_dt,
            Invoice.invoice_date <= end_dt,
        ).group_by(
            cast(Invoice.invoice_date, Date),
        ).order_by(
            cast(Invoice.invoice_date, Date),
        ).all()

        data = [
            {
                'date': row.sale_date.isoformat(),
                'total_sales': float(row.total_sales),
                'bill_count': int(row.bill_count),
            }
            for row in rows
        ]

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# API: Product-wise Sales
# ---------------------------------------------------------------------------

@reports_bp.route('/api/reports/product-sales')
@login_required
@admin_required
def product_sales():
    """Product-wise sales breakdown for the date range."""
    try:
        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        start, end, start_dt, end_dt = _parse_date_range()

        rows = db.session.query(
            InvoiceItem.product_name,
            func.sum(InvoiceItem.quantity).label('quantity_sold'),
            func.sum(InvoiceItem.total_amount).label('total_amount'),
        ).join(
            Invoice, Invoice.id == InvoiceItem.invoice_id,
        ).filter(
            Invoice.store_id == store.id,
            Invoice.status == 'completed',
            Invoice.invoice_date >= start_dt,
            Invoice.invoice_date <= end_dt,
        ).group_by(
            InvoiceItem.product_name,
        ).order_by(
            func.sum(InvoiceItem.total_amount).desc(),
        ).all()

        data = [
            {
                'product_name': row.product_name,
                'quantity_sold': float(row.quantity_sold),
                'total_amount': float(row.total_amount),
            }
            for row in rows
        ]

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# API: Category-wise Sales
# ---------------------------------------------------------------------------

@reports_bp.route('/api/reports/category-sales')
@login_required
@admin_required
def category_sales():
    """Category-wise sales breakdown for the date range."""
    try:
        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        start, end, start_dt, end_dt = _parse_date_range()

        rows = db.session.query(
            func.coalesce(Category.name, 'Uncategorised').label('category_name'),
            func.sum(InvoiceItem.quantity).label('quantity_sold'),
            func.sum(InvoiceItem.total_amount).label('total_amount'),
            func.count(func.distinct(InvoiceItem.product_id)).label('product_count'),
        ).select_from(InvoiceItem).join(
            Invoice, Invoice.id == InvoiceItem.invoice_id,
        ).outerjoin(
            Product, Product.id == InvoiceItem.product_id,
        ).outerjoin(
            Category, Category.id == Product.category_id,
        ).filter(
            Invoice.store_id == store.id,
            Invoice.status == 'completed',
            Invoice.invoice_date >= start_dt,
            Invoice.invoice_date <= end_dt,
        ).group_by(
            Category.name,
        ).order_by(
            func.sum(InvoiceItem.total_amount).desc(),
        ).all()

        data = [
            {
                'category_name': row.category_name,
                'quantity_sold': float(row.quantity_sold),
                'total_amount': float(row.total_amount),
                'product_count': int(row.product_count),
            }
            for row in rows
        ]

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# API: GST Report
# ---------------------------------------------------------------------------

@reports_bp.route('/api/reports/gst-report')
@login_required
@admin_required
def gst_report():
    """GST tax summary grouped by GST rate for the date range."""
    try:
        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        start, end, start_dt, end_dt = _parse_date_range()

        rows = db.session.query(
            InvoiceTax.gst_percentage,
            func.sum(InvoiceTax.taxable_amount).label('taxable_amount'),
            func.sum(InvoiceTax.cgst_amount).label('cgst_amount'),
            func.sum(InvoiceTax.sgst_amount).label('sgst_amount'),
            func.sum(InvoiceTax.igst_amount).label('igst_amount'),
            func.sum(InvoiceTax.cess_amount).label('cess_amount'),
            func.sum(InvoiceTax.total_tax).label('total_tax'),
        ).join(
            Invoice, Invoice.id == InvoiceTax.invoice_id,
        ).filter(
            Invoice.store_id == store.id,
            Invoice.status == 'completed',
            Invoice.invoice_date >= start_dt,
            Invoice.invoice_date <= end_dt,
        ).group_by(
            InvoiceTax.gst_percentage,
        ).order_by(
            InvoiceTax.gst_percentage,
        ).all()

        data = [
            {
                'gst_percentage': float(row.gst_percentage),
                'taxable_amount': float(row.taxable_amount),
                'cgst_amount': float(row.cgst_amount),
                'sgst_amount': float(row.sgst_amount),
                'igst_amount': float(row.igst_amount),
                'cess_amount': float(row.cess_amount),
                'total_tax': float(row.total_tax),
            }
            for row in rows
        ]

        return jsonify({
            'success': True,
            'data': data,
            'start_date': start.isoformat(),
            'end_date': end.isoformat(),
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# API: Payment Method Report
# ---------------------------------------------------------------------------

@reports_bp.route('/api/reports/payment-report')
@login_required
@admin_required
def payment_report():
    """Payment method breakdown for the date range."""
    try:
        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        start, end, start_dt, end_dt = _parse_date_range()

        rows = db.session.query(
            Payment.payment_method,
            func.count(Payment.id).label('transaction_count'),
            func.sum(Payment.amount).label('total_amount'),
        ).join(
            Invoice, Invoice.id == Payment.invoice_id,
        ).filter(
            Payment.store_id == store.id,
            Payment.status == 'completed',
            Invoice.status == 'completed',
            Invoice.invoice_date >= start_dt,
            Invoice.invoice_date <= end_dt,
        ).group_by(
            Payment.payment_method,
        ).order_by(
            func.sum(Payment.amount).desc(),
        ).all()

        data = [
            {
                'payment_method': row.payment_method,
                'transaction_count': int(row.transaction_count),
                'total_amount': float(row.total_amount),
            }
            for row in rows
        ]

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# API: Inventory Valuation Report
# ---------------------------------------------------------------------------

@reports_bp.route('/api/reports/inventory-report')
@login_required
@admin_required
def inventory_report():
    """Inventory valuation report – all products with stock value."""
    try:
        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        products = Product.query.filter(
            Product.store_id == store.id,
            Product.is_active == True,
        ).order_by(Product.name).all()

        data = []
        total_stock_value = Decimal('0.00')
        total_retail_value = Decimal('0.00')

        for p in products:
            cost_value = (p.purchase_price or Decimal('0.00')) * (p.stock_quantity or Decimal('0.000'))
            retail_value = (p.selling_price or Decimal('0.00')) * (p.stock_quantity or Decimal('0.000'))
            total_stock_value += cost_value
            total_retail_value += retail_value

            data.append({
                'id': p.id,
                'name': p.name,
                'barcode': p.barcode or '',
                'category': p.category.name if p.category else '',
                'stock_quantity': float(p.stock_quantity),
                'unit': p.unit,
                'purchase_price': float(p.purchase_price),
                'selling_price': float(p.selling_price),
                'cost_value': float(cost_value),
                'retail_value': float(retail_value),
                'is_low_stock': p.is_low_stock,
                'is_out_of_stock': p.is_out_of_stock,
            })

        return jsonify({
            'success': True,
            'data': data,
            'summary': {
                'total_products': len(data),
                'total_stock_value': float(total_stock_value),
                'total_retail_value': float(total_retail_value),
            },
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# API: Low Stock Report
# ---------------------------------------------------------------------------

@reports_bp.route('/api/reports/low-stock')
@login_required
@admin_required
def low_stock():
    """Products with stock at or below the minimum stock level."""
    try:
        store = Store.query.get(current_user.store_id)
        if not store:
            return jsonify({'success': False, 'message': 'Store not found'}), 404

        products = get_low_stock_products(store.id, limit=100)

        data = [
            {
                'id': p.id,
                'name': p.name,
                'barcode': p.barcode or '',
                'category': p.category.name if p.category else '',
                'stock_quantity': float(p.stock_quantity),
                'min_stock_level': float(p.min_stock_level),
                'unit': p.unit,
                'is_out_of_stock': p.is_out_of_stock,
            }
            for p in products
        ]

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
