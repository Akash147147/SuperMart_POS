"""Store, BillingCounter, and StoreSetting models."""
from datetime import datetime, timezone
from .base import db


class Store(db.Model):
    __tablename__ = 'stores'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    state_code = db.Column(db.String(5))
    pincode = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(150))
    gstin = db.Column(db.String(15))
    logo_path = db.Column(db.String(300))
    invoice_prefix = db.Column(db.String(10), default='INV')
    invoice_start_number = db.Column(db.Integer, default=1)
    current_invoice_number = db.Column(db.Integer, default=0)
    currency = db.Column(db.String(5), default='INR')
    tax_type = db.Column(db.String(20), default='intra-state')  # intra-state or inter-state
    receipt_footer = db.Column(db.Text, default='Thank You! Visit Again!')
    receipt_paper_width = db.Column(db.String(10), default='80mm')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    counters = db.relationship('BillingCounter', backref='store', lazy='dynamic')
    users = db.relationship('User', backref='store', lazy='dynamic')
    products = db.relationship('Product', backref='store', lazy='dynamic')
    invoices = db.relationship('Invoice', backref='store', lazy='dynamic')

    def get_next_invoice_number(self):
        """Get and increment the next invoice number atomically."""
        self.current_invoice_number += 1
        return f"{self.invoice_prefix}{self.current_invoice_number:06d}"

    def __repr__(self):
        return f'<Store {self.name}>'


class BillingCounter(db.Model):
    __tablename__ = 'billing_counters'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    invoices = db.relationship('Invoice', backref='counter', lazy='dynamic')

    def __repr__(self):
        return f'<Counter {self.name}>'


class StoreSetting(db.Model):
    __tablename__ = 'store_settings'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    setting_key = db.Column(db.String(100), nullable=False)
    setting_value = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('store_id', 'setting_key', name='uq_store_setting'),
    )

    def __repr__(self):
        return f'<StoreSetting {self.setting_key}>'

