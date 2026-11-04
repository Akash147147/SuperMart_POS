"""Inventory management service."""
from decimal import Decimal
from models.base import db
from models.product import Product
from models.inventory import StockMovement


def stock_in(product_id, quantity, store_id, user_id, notes=''):
    """Add stock to a product."""
    product = db.session.get(Product, product_id)
    if not product:
        raise ValueError(f"Product {product_id} not found")

    qty = Decimal(str(quantity))
    qty_before = product.stock_quantity
    product.stock_quantity += qty

    movement = StockMovement(
        store_id=store_id,
        product_id=product_id,
        movement_type='stock_in',
        quantity_change=qty,
        quantity_before=qty_before,
        quantity_after=product.stock_quantity,
        reference_type='manual',
        notes=notes,
        created_by=user_id,
    )
    db.session.add(movement)
    db.session.commit()
    return product


def stock_adjustment(product_id, new_quantity, store_id, user_id, reason=''):
    """Adjust stock to a specific quantity."""
    product = db.session.get(Product, product_id)
    if not product:
        raise ValueError(f"Product {product_id} not found")

    new_qty = Decimal(str(new_quantity))
    qty_before = product.stock_quantity
    change = new_qty - qty_before
    product.stock_quantity = new_qty

    movement = StockMovement(
        store_id=store_id,
        product_id=product_id,
        movement_type='adjustment',
        quantity_change=change,
        quantity_before=qty_before,
        quantity_after=new_qty,
        reference_type='manual',
        notes=reason,
        created_by=user_id,
    )
    db.session.add(movement)
    db.session.commit()
    return product


def record_damaged(product_id, quantity, store_id, user_id, notes=''):
    """Record damaged/wastage stock."""
    product = db.session.get(Product, product_id)
    if not product:
        raise ValueError(f"Product {product_id} not found")

    qty = Decimal(str(quantity))
    qty_before = product.stock_quantity
    product.stock_quantity -= qty

    movement = StockMovement(
        store_id=store_id,
        product_id=product_id,
        movement_type='damaged',
        quantity_change=-qty,
        quantity_before=qty_before,
        quantity_after=product.stock_quantity,
        reference_type='manual',
        notes=notes,
        created_by=user_id,
    )
    db.session.add(movement)
    db.session.commit()
    return product


def get_stock_movements(product_id=None, store_id=None, movement_type=None,
                        start_date=None, end_date=None, limit=100):
    """Get stock movement history."""
    query = StockMovement.query
    
    if store_id:
        query = query.filter_by(store_id=store_id)
    if product_id:
        query = query.filter_by(product_id=product_id)
    if movement_type:
        query = query.filter_by(movement_type=movement_type)
    if start_date:
        query = query.filter(StockMovement.created_at >= start_date)
    if end_date:
        query = query.filter(StockMovement.created_at <= end_date)

    return query.order_by(StockMovement.created_at.desc()).limit(limit).all()


def get_low_stock_products(store_id, limit=50):
    """Get products with stock below minimum level."""
    return Product.query.filter(
        Product.store_id == store_id,
        Product.is_active == True,
        Product.stock_quantity <= Product.min_stock_level,
    ).order_by(Product.stock_quantity.asc()).limit(limit).all()


def get_out_of_stock_products(store_id, limit=50):
    """Get products with zero stock."""
    return Product.query.filter(
        Product.store_id == store_id,
        Product.is_active == True,
        Product.stock_quantity <= 0,
    ).limit(limit).all()

