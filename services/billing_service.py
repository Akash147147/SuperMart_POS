"""Billing service - handles cart calculations and invoice creation."""
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from models.base import db
from models.product import Product
from models.invoice import Invoice, InvoiceItem, InvoiceTax
from models.payment import Payment
from models.inventory import StockMovement
from services.gst_service import calculate_item_tax, calculate_bill_taxes, round_to_nearest

TWO_PLACES = Decimal('0.01')


def lookup_product_by_barcode(barcode, store_id):
    """Find product by barcode."""
    product = Product.query.filter_by(
        barcode=barcode, store_id=store_id, is_active=True
    ).first()
    return product


def search_products(query, store_id, limit=20):
    """Search products by name or barcode."""
    products = Product.query.filter(
        Product.store_id == store_id,
        Product.is_active == True,
        db.or_(
            Product.name.ilike(f'%{query}%'),
            Product.barcode.ilike(f'%{query}%'),
            Product.hsn_code.ilike(f'%{query}%'),
        )
    ).limit(limit).all()
    return [p.to_dict() for p in products]


def calculate_cart_totals(cart_items, store):
    """
    Calculate all totals for the cart.
    
    cart_items: list of dicts with product_id, quantity, discount_amount, discount_percentage
    Returns: full bill calculation with items and tax summary
    """
    tax_type = store.tax_type or 'intra-state'
    items_result = []
    all_tax_data = []
    subtotal = Decimal('0.00')
    total_discount = Decimal('0.00')
    total_quantity = Decimal('0.000')
    serial = 0

    for item in cart_items:
        prod_id = item.get('product_id') or item.get('id')
        product = None
        if prod_id:
            try:
                product = db.session.get(Product, int(prod_id))
            except (ValueError, TypeError):
                product = None
        if not product and item.get('barcode'):
            product = Product.query.filter_by(barcode=item['barcode'], store_id=store.id).first()
        if not product:
            continue

        serial += 1
        qty = Decimal(str(item.get('quantity', 1)))
        item_discount_pct = Decimal(str(item.get('discount_percentage', 0)))
        item_discount_amt = Decimal(str(item.get('discount_amount', 0)))

        # Calculate line discount
        line_total = (product.selling_price * qty).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        
        if item_discount_pct > Decimal('0'):
            item_discount_amt = (line_total * item_discount_pct / Decimal('100')).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP)

        tax_data = calculate_item_tax(
            selling_price=product.selling_price,
            quantity=qty,
            gst_percentage=product.gst_percentage,
            cess_percentage=product.cess_percentage,
            discount_amount=item_discount_amt,
            tax_type=tax_type,
            is_gst_exempt=product.is_gst_exempt,
        )
        all_tax_data.append(tax_data)

        subtotal += line_total
        total_discount += item_discount_amt
        total_quantity += qty

        items_result.append({
            'serial_number': serial,
            'product_id': product.id,
            'product_name': product.name,
            'barcode': product.barcode or '',
            'hsn_code': product.hsn_code or '',
            'unit': product.unit,
            'quantity': str(qty),
            'mrp': str(product.mrp),
            'selling_price': str(product.selling_price),
            'discount_amount': str(item_discount_amt),
            'discount_percentage': str(item_discount_pct),
            'gst_percentage': str(product.gst_percentage),
            'is_gst_exempt': product.is_gst_exempt,
            'taxable_amount': str(tax_data['taxable_amount']),
            'cgst_amount': str(tax_data['cgst_amount']),
            'sgst_amount': str(tax_data['sgst_amount']),
            'igst_amount': str(tax_data['igst_amount']),
            'cess_amount': str(tax_data['cess_amount']),
            'total_tax': str(tax_data['total_tax']),
            'total_amount': str(tax_data['total_amount']),
        })

    # Bill-level tax summary
    bill_taxes = calculate_bill_taxes(all_tax_data, tax_type)
    
    net_amount = subtotal - total_discount + bill_taxes['total_tax']
    final_amount, round_off = round_to_nearest(net_amount)

    return {
        'items': items_result,
        'subtotal': str(subtotal.quantize(TWO_PLACES)),
        'total_discount': str(total_discount.quantize(TWO_PLACES)),
        'taxable_amount': str(bill_taxes['total_taxable']),
        'cgst_total': str(bill_taxes['total_cgst']),
        'sgst_total': str(bill_taxes['total_sgst']),
        'igst_total': str(bill_taxes['total_igst']),
        'cess_total': str(bill_taxes['total_cess']),
        'tax_total': str(bill_taxes['total_tax']),
        'net_amount': str(net_amount.quantize(TWO_PLACES)),
        'round_off': str(round_off),
        'final_amount': str(final_amount.quantize(TWO_PLACES)),
        'total_items': serial,
        'total_quantity': str(total_quantity.quantize(Decimal('0.001'))),
        'tax_groups': [{k: str(v) for k, v in g.items()} for g in bill_taxes['tax_groups']],
        'tax_type': tax_type,
    }


def complete_sale(cart_items, payment_data, store, cashier, counter=None,
                  customer_id=None, bill_discount_pct=Decimal('0'),
                  bill_discount_amt=Decimal('0'), notes=None):
    """
    Complete a sale transaction atomically.
    
    Creates invoice, invoice items, tax records, payment records.
    Deducts inventory only on success.
    Returns the created invoice or raises exception.
    """
    tax_type = store.tax_type or 'intra-state'

    # Generate invoice number
    invoice_number = store.get_next_invoice_number()

    # Create invoice
    invoice = Invoice(
        store_id=store.id,
        counter_id=counter.id if counter else None,
        invoice_number=invoice_number,
        customer_id=customer_id,
        cashier_id=cashier.id,
        tax_type=tax_type,
        notes=notes,
        invoice_date=datetime.now(timezone.utc),
    )

    all_tax_data = []
    subtotal = Decimal('0.00')
    total_discount = Decimal('0.00')
    total_quantity = Decimal('0.000')
    serial = 0

    items_to_deduct = []  # (product, quantity) pairs

    for item in cart_items:
        prod_id = item.get('product_id') or item.get('id')
        product = None
        if prod_id:
            try:
                product = db.session.get(Product, int(prod_id))
            except (ValueError, TypeError):
                product = None
        if not product and item.get('barcode'):
            product = Product.query.filter_by(barcode=item['barcode'], store_id=store.id).first()
        if not product or not product.is_active:
            raise ValueError(f"Product {item.get('product_name') or prod_id} not found or inactive")

        serial += 1
        qty = Decimal(str(item.get('quantity', 1)))
        item_discount_pct = Decimal(str(item.get('discount_percentage', 0)))
        item_discount_amt = Decimal(str(item.get('discount_amount', 0)))

        line_total = (product.selling_price * qty).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        if item_discount_pct > Decimal('0'):
            item_discount_amt = (line_total * item_discount_pct / Decimal('100')).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP)

        tax_data = calculate_item_tax(
            selling_price=product.selling_price,
            quantity=qty,
            gst_percentage=product.gst_percentage,
            cess_percentage=product.cess_percentage,
            discount_amount=item_discount_amt,
            tax_type=tax_type,
            is_gst_exempt=product.is_gst_exempt,
        )
        all_tax_data.append(tax_data)

        subtotal += line_total
        total_discount += item_discount_amt
        total_quantity += qty

        inv_item = InvoiceItem(
            serial_number=serial,
            product_id=product.id,
            product_name=product.name,
            barcode=product.barcode,
            hsn_code=product.hsn_code,
            unit=product.unit,
            quantity=qty,
            mrp=product.mrp,
            selling_price=product.selling_price,
            discount_amount=item_discount_amt,
            discount_percentage=item_discount_pct,
            taxable_amount=tax_data['taxable_amount'],
            gst_percentage=product.gst_percentage,
            cgst_amount=tax_data['cgst_amount'],
            sgst_amount=tax_data['sgst_amount'],
            igst_amount=tax_data['igst_amount'],
            cess_percentage=product.cess_percentage,
            cess_amount=tax_data['cess_amount'],
            total_amount=tax_data['total_amount'],
            is_gst_exempt=product.is_gst_exempt,
        )
        invoice.items.append(inv_item)
        items_to_deduct.append((product, qty))

    # Apply bill-level discount
    bill_discount_pct = Decimal(str(bill_discount_pct))
    bill_discount_amt = Decimal(str(bill_discount_amt))
    if bill_discount_pct > Decimal('0'):
        bill_discount_amt = (subtotal * bill_discount_pct / Decimal('100')).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP)
    total_discount += bill_discount_amt

    # Bill tax summary
    bill_taxes = calculate_bill_taxes(all_tax_data, tax_type)

    net_amount = subtotal - total_discount + bill_taxes['total_tax']
    final_amount, round_off = round_to_nearest(net_amount)

    # Set invoice totals
    invoice.subtotal = subtotal.quantize(TWO_PLACES)
    invoice.discount_amount = total_discount.quantize(TWO_PLACES)
    invoice.discount_percentage = bill_discount_pct
    invoice.taxable_amount = bill_taxes['total_taxable']
    invoice.cgst_total = bill_taxes['total_cgst']
    invoice.sgst_total = bill_taxes['total_sgst']
    invoice.igst_total = bill_taxes['total_igst']
    invoice.cess_total = bill_taxes['total_cess']
    invoice.tax_total = bill_taxes['total_tax']
    invoice.net_amount = net_amount.quantize(TWO_PLACES)
    invoice.round_off = round_off
    invoice.final_amount = final_amount
    invoice.total_items = serial
    invoice.total_quantity = total_quantity
    invoice.status = 'completed'

    # Create tax summary records
    for tg in bill_taxes['tax_groups']:
        inv_tax = InvoiceTax(
            gst_percentage=tg['gst_percentage'],
            taxable_amount=tg['taxable_amount'],
            cgst_rate=tg['cgst_rate'],
            cgst_amount=tg['cgst_amount'],
            sgst_rate=tg['sgst_rate'],
            sgst_amount=tg['sgst_amount'],
            igst_rate=tg['igst_rate'],
            igst_amount=tg['igst_amount'],
            cess_rate=tg['cess_rate'],
            cess_amount=tg['cess_amount'],
            total_tax=tg['total_tax'],
        )
        invoice.taxes.append(inv_tax)

    # Validate payment
    total_paid = Decimal('0.00')
    for pd in payment_data:
        pay_amount = Decimal(str(pd['amount']))
        total_paid += pay_amount

        payment = Payment(
            store_id=store.id,
            payment_method=pd['method'],
            amount=pay_amount,
            reference_number=pd.get('reference', ''),
            amount_received=Decimal(str(pd.get('amount_received', pay_amount))),
            change_returned=Decimal(str(pd.get('change_returned', 0))),
            status='completed',
        )
        invoice.payments.append(payment)

    if total_paid < (final_amount - Decimal('0.50')):
        raise ValueError(
            f"Payment amount ({total_paid}) is less than bill amount ({final_amount})"
        )

    # Save invoice
    db.session.add(invoice)

    # Deduct inventory ONLY after invoice is valid
    for product, qty in items_to_deduct:
        qty_before = product.stock_quantity
        product.stock_quantity = product.stock_quantity - qty
        
        movement = StockMovement(
            store_id=store.id,
            product_id=product.id,
            movement_type='sale',
            quantity_change=-qty,
            quantity_before=qty_before,
            quantity_after=product.stock_quantity,
            reference_type='invoice',
            reference_id=None,  # Will be set after flush
            created_by=cashier.id,
        )
        db.session.add(movement)

    # Commit everything atomically
    db.session.flush()
    
    # Update stock movement references with invoice id
    for movement in db.session.new:
        if isinstance(movement, StockMovement) and movement.reference_id is None:
            movement.reference_id = invoice.id

    db.session.commit()

    return invoice

