"""Product and Category models."""
from datetime import datetime, timezone
from decimal import Decimal
from .base import db


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    products = db.relationship('Product', backref='category', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('store_id', 'name', name='uq_store_category'),
    )

    def __repr__(self):
        return f'<Category {self.name}>'


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    barcode = db.Column(db.String(50), index=True)  # nullable for products without barcodes
    hsn_code = db.Column(db.String(20))
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    brand = db.Column(db.String(100))
    size_weight = db.Column(db.String(50))  # e.g., "1KG", "500ML"
    unit = db.Column(db.String(20), default='pcs')  # pcs, kg, g, l, ml, etc.
    mrp = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal('0.00'))
    selling_price = db.Column(db.Numeric(12, 2), nullable=False, default=Decimal('0.00'))
    purchase_price = db.Column(db.Numeric(12, 2), default=Decimal('0.00'))
    gst_percentage = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    cess_percentage = db.Column(db.Numeric(5, 2), default=Decimal('0.00'))
    is_gst_exempt = db.Column(db.Boolean, default=False)
    stock_quantity = db.Column(db.Numeric(12, 3), default=Decimal('0.000'))
    min_stock_level = db.Column(db.Numeric(12, 3), default=Decimal('5.000'))
    is_active = db.Column(db.Boolean, default=True)
    sold_by_weight = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    invoice_items = db.relationship('InvoiceItem', backref='product', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('store_id', 'barcode', name='uq_store_barcode'),
        db.Index('ix_product_name', 'store_id', 'name'),
    )

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.min_stock_level

    @property
    def is_out_of_stock(self):
        return self.stock_quantity <= 0

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'barcode': self.barcode or '',
            'hsn_code': self.hsn_code or '',
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else '',
            'brand': self.brand or '',
            'size_weight': self.size_weight or '',
            'unit': self.unit,
            'mrp': str(self.mrp),
            'selling_price': str(self.selling_price),
            'purchase_price': str(self.purchase_price),
            'gst_percentage': str(self.gst_percentage),
            'cess_percentage': str(self.cess_percentage),
            'is_gst_exempt': self.is_gst_exempt,
            'stock_quantity': str(self.stock_quantity),
            'min_stock_level': str(self.min_stock_level),
            'is_active': self.is_active,
            'sold_by_weight': self.sold_by_weight,
            'is_low_stock': self.is_low_stock,
            'is_out_of_stock': self.is_out_of_stock,
        }

    def __repr__(self):
        return f'<Product {self.name}>'

