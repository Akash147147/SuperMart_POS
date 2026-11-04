"""Supplier, Purchase, and PurchaseItem models."""
from datetime import datetime, timezone
from decimal import Decimal
from .base import db


class Supplier(db.Model):
    __tablename__ = 'suppliers'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(150))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(150))
    address = db.Column(db.Text)
    gstin = db.Column(db.String(15))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    purchases = db.relationship('Purchase', backref='supplier', lazy='dynamic')

    def __repr__(self):
        return f'<Supplier {self.name}>'


class Purchase(db.Model):
    __tablename__ = 'purchases'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    purchase_number = db.Column(db.String(30))
    purchase_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    total_amount = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    status = db.Column(db.String(20), default='completed')
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    items = db.relationship('PurchaseItem', backref='purchase', lazy='select',
                           cascade='all, delete-orphan')
    creator = db.relationship('User', backref='purchases_created')

    def __repr__(self):
        return f'<Purchase {self.purchase_number}>'


class PurchaseItem(db.Model):
    __tablename__ = 'purchase_items'

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Numeric(12, 3), nullable=False)
    purchase_price = db.Column(db.Numeric(12, 2), nullable=False)
    total_amount = db.Column(db.Numeric(14, 2))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    product = db.relationship('Product', backref='purchase_items')

    def __repr__(self):
        return f'<PurchaseItem product={self.product_id}>'

