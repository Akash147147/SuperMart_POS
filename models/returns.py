"""Return and ReturnItem models."""
from datetime import datetime, timezone
from decimal import Decimal
from .base import db


class Return(db.Model):
    __tablename__ = 'returns'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    return_number = db.Column(db.String(30), unique=True, nullable=False)
    return_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    total_refund = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='completed')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    invoice = db.relationship('Invoice', backref='returns')
    creator = db.relationship('User', backref='returns_processed')
    items = db.relationship('ReturnItem', backref='return_record', lazy='select',
                           cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Return {self.return_number}>'


class ReturnItem(db.Model):
    __tablename__ = 'return_items'

    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey('returns.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    invoice_item_id = db.Column(db.Integer, db.ForeignKey('invoice_items.id'))
    quantity = db.Column(db.Numeric(12, 3), nullable=False)
    refund_amount = db.Column(db.Numeric(14, 2), nullable=False)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    product = db.relationship('Product', backref='return_items')

    def __repr__(self):
        return f'<ReturnItem product={self.product_id}>'

