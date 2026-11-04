"""Inventory and StockMovement models."""
from datetime import datetime, timezone
from decimal import Decimal
from .base import db


class Inventory(db.Model):
    """Tracks current inventory levels - mirrors product.stock_quantity but with store context."""
    __tablename__ = 'inventory'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Numeric(12, 3), default=Decimal('0.000'))
    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc))

    product = db.relationship('Product', backref='inventory_record')

    __table_args__ = (
        db.UniqueConstraint('store_id', 'product_id', name='uq_store_product_inventory'),
    )

    def __repr__(self):
        return f'<Inventory product={self.product_id} qty={self.quantity}>'


class StockMovement(db.Model):
    """Records all stock changes for audit trail."""
    __tablename__ = 'stock_movements'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    movement_type = db.Column(db.String(30), nullable=False)
    # Types: sale, purchase, stock_in, adjustment, return, damaged, opening
    quantity_change = db.Column(db.Numeric(12, 3), nullable=False)
    quantity_before = db.Column(db.Numeric(12, 3), nullable=False)
    quantity_after = db.Column(db.Numeric(12, 3), nullable=False)
    reference_type = db.Column(db.String(30))  # invoice, purchase, manual
    reference_id = db.Column(db.Integer)
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    product = db.relationship('Product', backref='stock_movements')
    user = db.relationship('User', backref='stock_movements')

    __table_args__ = (
        db.Index('ix_stock_movement_product', 'store_id', 'product_id'),
        db.Index('ix_stock_movement_date', 'created_at'),
    )

    def __repr__(self):
        return f'<StockMovement {self.movement_type} {self.quantity_change}>'

