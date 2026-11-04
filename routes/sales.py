"""Sales routes and order history."""
from functools import wraps
from flask import Blueprint, request, jsonify, render_template, send_file
from flask_login import login_required, current_user
from models.store import Store
from services.invoice_service import (
    get_invoice_by_id, get_invoices, void_invoice, generate_invoice_pdf, get_amount_in_words
)

sales_bp = Blueprint('sales', __name__)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({'success': False, 'message': 'Admin privilege required'}), 403
        return f(*args, **kwargs)
    return decorated_function


@sales_bp.route('/sales')
@login_required
def sales_page():
    return render_template('sales.html')


@sales_bp.route('/api/sales/invoices', methods=['GET'])
@login_required
def list_invoices():
    store_id = current_user.store_id or 1
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    payment_method = request.args.get('payment_method')

    pagination = get_invoices(
        store_id=store_id,
        status=status,
        payment_method=payment_method,
        page=page,
        per_page=per_page
    )

    return jsonify({
        'success': True,
        'invoices': [inv.to_dict() for inv in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    })


@sales_bp.route('/api/sales/invoice/<int:id>', methods=['GET'])
@login_required
def get_invoice(id):
    invoice = get_invoice_by_id(id)
    if not invoice:
        return jsonify({'success': False, 'message': 'Invoice not found'}), 404
    return jsonify({'success': True, 'invoice': invoice.to_dict()})


@sales_bp.route('/api/sales/invoice/<int:id>/receipt', methods=['GET'])
@login_required
def invoice_receipt(id):
    invoice = get_invoice_by_id(id)
    if not invoice:
        return "Invoice not found", 404
    store = Store.query.get(invoice.store_id) or Store.query.first()
    amount_words = get_amount_in_words(invoice.final_amount)
    return render_template(
        'receipt.html',
        invoice=invoice,
        store=store,
        amount_words=amount_words,
        paper_width=store.receipt_paper_width or '80mm'
    )


@sales_bp.route('/api/sales/invoice/<int:id>/pdf', methods=['GET'])
@login_required
def invoice_pdf(id):
    invoice = get_invoice_by_id(id)
    if not invoice:
        return "Invoice not found", 404
    store = Store.query.get(invoice.store_id) or Store.query.first()
    try:
        pdf_stream = generate_invoice_pdf(invoice, store)
        return send_file(
            pdf_stream,
            mimetype='application/pdf',
            as_attachment=False,
            download_name=f"Invoice_{invoice.invoice_number}.pdf"
        )
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@sales_bp.route('/api/sales/invoice/<int:id>/void', methods=['POST'])
@login_required
@admin_required
def void_inv(id):
    data = request.get_json() or {}
    reason = data.get('reason', 'Cancelled by administrator')
    try:
        inv = void_invoice(id, user_id=current_user.id, reason=reason)
        return jsonify({'success': True, 'message': f'Invoice {inv.invoice_number} voided successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

