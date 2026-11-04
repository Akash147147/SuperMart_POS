"""Invoice service - retrieval and PDF generation."""
from decimal import Decimal
from io import BytesIO
from datetime import datetime

try:
    from num2words import num2words
except ImportError:
    num2words = None

from models.invoice import Invoice
from models.store import Store


def get_amount_in_words(amount):
    """Convert amount to words in Indian format with graceful fallback."""
    amount = Decimal(str(amount))
    rupees = int(amount)
    paise = int((amount - rupees) * 100)

    if num2words:
        try:
            words = num2words(rupees, lang='en_IN').upper()
            result = f"{words} RUPEES"
            if paise > 0:
                paise_words = num2words(paise, lang='en_IN').upper()
                result += f" AND {paise_words} PAISE"
            result += " ONLY"
            return result
        except Exception:
            pass
    return f"{rupees} RUPEES AND {paise:02d} PAISE ONLY"


def get_invoice_by_number(invoice_number, store_id=None):
    """Get invoice by number."""
    query = Invoice.query.filter_by(invoice_number=invoice_number)
    if store_id:
        query = query.filter_by(store_id=store_id)
    return query.first()


def get_invoice_by_id(invoice_id):
    """Get invoice by ID."""
    return Invoice.query.get(invoice_id)


def get_invoices(store_id, start_date=None, end_date=None, status=None,
                 payment_method=None, cashier_id=None, page=1, per_page=50):
    """Get paginated invoices."""
    query = Invoice.query.filter_by(store_id=store_id)
    
    if start_date:
        query = query.filter(Invoice.invoice_date >= start_date)
    if end_date:
        query = query.filter(Invoice.invoice_date <= end_date)
    if status:
        query = query.filter_by(status=status)
    if cashier_id:
        query = query.filter_by(cashier_id=cashier_id)
    if payment_method:
        query = query.join(Invoice.payments).filter(
            Invoice.payments.any(payment_method=payment_method)
        )

    return query.order_by(Invoice.invoice_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )


def void_invoice(invoice_id, user_id, reason=''):
    """Void/cancel an invoice. Does NOT delete - marks as void."""
    from models.base import db
    from models.inventory import StockMovement
    
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        raise ValueError("Invoice not found")
    if invoice.status == 'void':
        raise ValueError("Invoice already voided")

    invoice.status = 'void'
    invoice.notes = (invoice.notes or '') + f"\nVoided: {reason}"

    # Restore stock
    for item in invoice.items:
        product = item.product
        if product:
            qty_before = product.stock_quantity
            product.stock_quantity += item.quantity
            
            movement = StockMovement(
                store_id=invoice.store_id,
                product_id=product.id,
                movement_type='return',
                quantity_change=item.quantity,
                quantity_before=qty_before,
                quantity_after=product.stock_quantity,
                reference_type='void_invoice',
                reference_id=invoice.id,
                notes=f"Stock restored from voided invoice {invoice.invoice_number}",
                created_by=user_id,
            )
            db.session.add(movement)

    db.session.commit()
    return invoice


def generate_invoice_pdf(invoice, store):
    """Generate a PDF invoice using ReportLab."""
    try:
        from reportlab.lib.pagesizes import A4, mm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm as unit_mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    except ImportError:
        raise RuntimeError("reportlab is required for PDF generation")

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=15 * unit_mm, bottomMargin=15 * unit_mm,
                            leftMargin=15 * unit_mm, rightMargin=15 * unit_mm)
    
    styles = getSampleStyleSheet()
    center_style = ParagraphStyle('center', parent=styles['Normal'], alignment=TA_CENTER)
    right_style = ParagraphStyle('right', parent=styles['Normal'], alignment=TA_RIGHT)
    title_style = ParagraphStyle('title_center', parent=styles['Title'], alignment=TA_CENTER, fontSize=16)

    elements = []

    # Header
    elements.append(Paragraph(store.name, title_style))
    if store.address:
        elements.append(Paragraph(store.address, center_style))
    if store.phone:
        elements.append(Paragraph(f"Phone: {store.phone}", center_style))
    if store.gstin:
        elements.append(Paragraph(f"GSTIN: {store.gstin}", center_style))
    elements.append(Spacer(1, 5 * unit_mm))
    elements.append(Paragraph("<b>TAX INVOICE</b>", title_style))
    elements.append(Spacer(1, 3 * unit_mm))

    # Bill info
    inv_date = invoice.invoice_date.strftime('%d-%b-%Y %I:%M %p') if invoice.invoice_date else ''
    info_data = [
        [f"Bill No: {invoice.invoice_number}", f"Date: {inv_date}"],
        [f"Cashier: {invoice.cashier.full_name if invoice.cashier else ''}", ''],
    ]
    if invoice.customer:
        info_data.append([f"Customer: {invoice.customer.name}", f"Phone: {invoice.customer.phone or ''}"])

    info_table = Table(info_data, colWidths=[doc.width * 0.5] * 2)
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 5 * unit_mm))

    # Items table
    header = ['#', 'Product', 'HSN', 'Qty', 'MRP', 'Price', 'Disc', 'GST%', 'Amount']
    table_data = [header]
    for item in invoice.items:
        table_data.append([
            str(item.serial_number),
            item.product_name[:25],
            item.hsn_code or '',
            str(item.quantity),
            str(item.mrp),
            str(item.selling_price),
            str(item.discount_amount),
            str(item.gst_percentage) + '%',
            str(item.total_amount),
        ])

    col_widths = [20, 100, 40, 30, 45, 45, 35, 35, 55]
    items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2744')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 5 * unit_mm))

    # Totals
    totals = [
        ['Subtotal', f'Rs. {invoice.subtotal}'],
        ['Discount', f'Rs. {invoice.discount_amount}'],
        ['Taxable Amount', f'Rs. {invoice.taxable_amount}'],
    ]
    if invoice.tax_type == 'intra-state':
        totals.append(['CGST', f'Rs. {invoice.cgst_total}'])
        totals.append(['SGST', f'Rs. {invoice.sgst_total}'])
    else:
        totals.append(['IGST', f'Rs. {invoice.igst_total}'])
    if invoice.cess_total and invoice.cess_total > 0:
        totals.append(['Cess', f'Rs. {invoice.cess_total}'])
    totals.append(['Round Off', f'Rs. {invoice.round_off}'])
    totals.append(['Net Amount', f'Rs. {invoice.final_amount}'])

    totals_table = Table(totals, colWidths=[doc.width * 0.7, doc.width * 0.3])
    totals_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 3 * unit_mm))

    # Amount in words
    words = get_amount_in_words(invoice.final_amount)
    elements.append(Paragraph(f"<b>In Words:</b> {words}", styles['Normal']))
    elements.append(Spacer(1, 3 * unit_mm))

    # Payment info
    for p in invoice.payments:
        elements.append(Paragraph(f"Payment: {p.payment_method.upper()} - Rs. {p.amount}", styles['Normal']))
    elements.append(Spacer(1, 3 * unit_mm))

    # Footer
    elements.append(Paragraph(f"Total Items: {invoice.total_items} | Total Qty: {invoice.total_quantity}", center_style))
    elements.append(Spacer(1, 3 * unit_mm))
    if store.receipt_footer:
        elements.append(Paragraph(store.receipt_footer, center_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer


