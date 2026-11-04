"""HeldBill model - for bills put on hold."""
from datetime import datetime, timezone
from .base import db


class HeldBill(db.Model):
    __tablename__ = 'held_bills'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    counter_id = db.Column(db.Integer, db.ForeignKey('billing_counters.id'))
    cashier_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    bill_data = db.Column(db.JSON, nullable=False)  # Stores complete cart state
    notes = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    cashier = db.relationship('User', backref='held_bills')
    customer = db.relationship('Customer', backref='held_bills')

    def __repr__(self):
        return f'<HeldBill {self.id}>'

