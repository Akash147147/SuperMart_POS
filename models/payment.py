"""Payment model."""
from datetime import datetime, timezone
from decimal import Decimal
from .base import db


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    payment_method = db.Column(db.String(30), nullable=False)
    # cash, upi, debit_card, credit_card, other
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    reference_number = db.Column(db.String(100))
    amount_received = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    change_returned = db.Column(db.Numeric(14, 2), default=Decimal('0.00'))
    status = db.Column(db.String(20), default='completed')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'payment_method': self.payment_method,
            'amount': str(self.amount),
            'reference_number': self.reference_number or '',
            'amount_received': str(self.amount_received),
            'change_returned': str(self.change_returned),
            'status': self.status,
        }

    def __repr__(self):
        return f'<Payment {self.payment_method} {self.amount}>'

