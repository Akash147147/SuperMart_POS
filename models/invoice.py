"""Invoice, InvoiceItem, and InvoiceTax models."""
from datetime import datetime, timezone
from decimal import Decimal
from .base import db


class Invoice(db.Model):
    __tablename__ = 'invoices'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    counter_id = db.Column(db.Integer, db.ForeignKey('billing_counters.id'))
    invoice_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    cashier_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Financial totals (Decimal for precision)
    subtotal = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    discount_amount = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    discount_percentage = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    taxable_amount = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    cgst_total = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    sgst_total = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    igst_total = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    cess_total = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    tax_total = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    net_amount = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    round_off = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    final_amount = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))

    total_items = db.Column(db.Integer, default=0)
    total_quantity = db.Column(db.Numeric(12, 3), default=Decimal('0.000'))

    status = db.Column(db.String(20), default='completed')
    # completed, cancelled, returned, void
    tax_type = db.Column(db.String(20), default='intra-state')

    notes = db.Column(db.Text)
    invoice_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    items = db.relationship('InvoiceItem', backref='invoice', lazy='select',
                           cascade='all, delete-orphan')
    taxes = db.relationship('InvoiceTax', backref='invoice', lazy='select',
                           cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='invoice', lazy='select',
                              cascade='all, delete-orphan')
    cashier = db.relationship('User', backref='invoices_created')

    __table_args__ = (
        db.Index('ix_invoice_date', 'store_id', 'invoice_date'),
        db.Index('ix_invoice_status', 'store_id', 'status'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'invoice_number': self.invoice_number,
            'customer': self.customer.to_dict() if self.customer else None,
            'cashier_name': self.cashier.full_name if self.cashier else '',
            'subtotal': str(self.subtotal),
            'discount_amount': str(self.discount_amount),
            'taxable_amount': str(self.taxable_amount),
            'cgst_total': str(self.cgst_total),
            'sgst_total': str(self.sgst_total),
            'igst_total': str(self.igst_total),
            'cess_total': str(self.cess_total),
            'tax_total': str(self.tax_total),
            'net_amount': str(self.net_amount),
            'round_off': str(self.round_off),
            'final_amount': str(self.final_amount),
            'total_items': self.total_items,
            'total_quantity': str(self.total_quantity),
            'status': self.status,
            'tax_type': self.tax_type,
            'invoice_date': self.invoice_date.isoformat() if self.invoice_date else '',
            'items': [item.to_dict() for item in self.items],
            'taxes': [tax.to_dict() for tax in self.taxes],
            'payments': [p.to_dict() for p in self.payments],
        }

    def __repr__(self):
        return f'<Invoice {self.invoice_number}>'


class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    serial_number = db.Column(db.Integer, default=1)

    # Snapshot product data at time of sale
    product_name = db.Column(db.String(200), nullable=False)
    barcode = db.Column(db.String(50))
    hsn_code = db.Column(db.String(20))
    unit = db.Column(db.String(20))

    quantity = db.Column(db.Numeric(12, 3), nullable=False, default=Decimal('1.000'))
    mrp = db.Column(db.Numeric(12, 2), nullable=False)
    selling_price = db.Column(db.Numeric(12, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))
    discount_percentage = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))

    taxable_amount = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    gst_percentage = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    cgst_amount = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))
    sgst_amount = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))
    igst_amount = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))
    cess_percentage = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    cess_amount = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))

    total_amount = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    is_gst_exempt = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'serial_number': self.serial_number,
            'product_name': self.product_name,
            'barcode': self.barcode or '',
            'hsn_code': self.hsn_code or '',
            'unit': self.unit or 'pcs',
            'quantity': str(self.quantity),
            'mrp': str(self.mrp),
            'selling_price': str(self.selling_price),
            'discount_amount': str(self.discount_amount),
            'discount_percentage': str(self.discount_percentage),
            'taxable_amount': str(self.taxable_amount),
            'gst_percentage': str(self.gst_percentage),
            'cgst_amount': str(self.cgst_amount),
            'sgst_amount': str(self.sgst_amount),
            'igst_amount': str(self.igst_amount),
            'cess_percentage': str(self.cess_percentage),
            'cess_amount': str(self.cess_amount),
            'total_amount': str(self.total_amount),
            'is_gst_exempt': self.is_gst_exempt,
        }

    def __repr__(self):
        return f'<InvoiceItem {self.product_name} x{self.quantity}>'


class InvoiceTax(db.Model):
    """GST summary per tax rate per invoice."""
    __tablename__ = 'invoice_taxes'

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    gst_percentage = db.Column(db.Numeric(5, 2), nullable=False)
    taxable_amount = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    cgst_rate = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    cgst_amount = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    sgst_rate = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    sgst_amount = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    igst_rate = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    igst_amount = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    cess_rate = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    cess_amount = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    total_tax = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))

    def to_dict(self):
        return {
            'gst_percentage': str(self.gst_percentage),
            'taxable_amount': str(self.taxable_amount),
            'cgst_rate': str(self.cgst_rate),
            'cgst_amount': str(self.cgst_amount),
            'sgst_rate': str(self.sgst_rate),
            'sgst_amount': str(self.sgst_amount),
            'igst_rate': str(self.igst_rate),
            'igst_amount': str(self.igst_amount),
            'cess_rate': str(self.cess_rate),
            'cess_amount': str(self.cess_amount),
            'total_tax': str(self.total_tax),
        }

    def __repr__(self):
        return f'<InvoiceTax {self.gst_percentage}%>'

