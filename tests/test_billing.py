"""Automated tests for product, inventory, barcode, and billing workflows."""
import unittest
from decimal import Decimal
from datetime import datetime, timezone
from app import create_app
from models.base import db
from models.user import User, Role
from models.store import Store, BillingCounter
from models.product import Product, Category
from models.inventory import StockMovement
from services.billing_service import calculate_cart_totals, complete_sale, lookup_product_by_barcode
from services.inventory_service import stock_in, stock_adjustment, record_damaged
from services.barcode_service import validate_ean13_checksum, clean_barcode, identify_barcode_format


class TestBillingAndInventory(unittest.TestCase):

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create base test data
        self.admin_role = Role(name='admin', description='Admin')
        self.cashier_role = Role(name='cashier', description='Cashier')
        db.session.add_all([self.admin_role, self.cashier_role])
        db.session.flush()

        self.store = Store(
            name='Test SuperMart',
            address='Test Address',
            gstin='27ABCDE1234F1Z5',
            tax_type='intra-state',
            receipt_paper_width='80mm'
        )
        db.session.add(self.store)
        db.session.flush()

        self.counter = BillingCounter(store_id=self.store.id, name='Counter 1')
        db.session.add(self.counter)
        db.session.flush()

        self.cashier = User(
            username='cashier_test',
            full_name='Test Cashier',
            role_id=self.cashier_role.id,
            store_id=self.store.id
        )
        self.cashier.set_password('pass123')
        db.session.add(self.cashier)

        # Create test product
        self.category = Category(store_id=self.store.id, name='Grocery')
        db.session.add(self.category)
        db.session.flush()

        self.product = Product(
            store_id=self.store.id,
            name='Fortune Sunflower Oil 1L',
            barcode='8901234567890',
            hsn_code='1512',
            category_id=self.category.id,
            unit='pcs',
            mrp=Decimal('150.00'),
            selling_price=Decimal('140.00'),
            purchase_price=Decimal('120.00'),
            gst_percentage=Decimal('5.00'),
            stock_quantity=Decimal('50.000'),
            min_stock_level=Decimal('5.000'),
            is_active=True
        )
        db.session.add(self.product)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_barcode_lookup(self):
        """Test scanning/looking up by barcode."""
        prod = lookup_product_by_barcode('8901234567890', self.store.id)
        self.assertIsNotNone(prod)
        self.assertEqual(prod.name, 'Fortune Sunflower Oil 1L')

    def test_cart_calculation(self):
        """Test cart totals calculation with GST."""
        cart_items = [{
            'product_id': self.product.id,
            'quantity': 2,
            'discount_amount': 0,
            'discount_percentage': 0
        }]
        totals = calculate_cart_totals(cart_items, self.store)
        self.assertEqual(totals['subtotal'], '280.00')
        # 5% GST on 280 = 14.00 (7.00 CGST + 7.00 SGST)
        self.assertEqual(totals['cgst_total'], '7.00')
        self.assertEqual(totals['sgst_total'], '7.00')
        self.assertEqual(totals['tax_total'], '14.00')
        self.assertEqual(totals['final_amount'], '294.00')

    def test_complete_sale_deducts_inventory_atomically(self):
        """Verify complete checkout creates invoice and deducts inventory."""
        initial_stock = self.product.stock_quantity  # 50
        cart_items = [{
            'product_id': self.product.id,
            'quantity': 3,
            'discount_amount': 0,
            'discount_percentage': 0
        }]
        # 3 * 140 = 420; 5% GST = 21.00; Final = 441.00
        payment_data = [{
            'method': 'cash',
            'amount': '441.00',
            'amount_received': '500.00',
            'change_returned': '59.00'
        }]

        invoice = complete_sale(
            cart_items=cart_items,
            payment_data=payment_data,
            store=self.store,
            cashier=self.cashier,
            counter=self.counter
        )

        self.assertIsNotNone(invoice.id)
        self.assertEqual(invoice.final_amount, Decimal('441.00'))
        self.assertEqual(invoice.total_items, 1)
        self.assertEqual(invoice.total_quantity, Decimal('3.000'))

        # Verify stock decreased by exactly 3
        reloaded_prod = Product.query.get(self.product.id)
        self.assertEqual(reloaded_prod.stock_quantity, initial_stock - Decimal('3.000'))

        # Verify stock movement record created
        movement = StockMovement.query.filter_by(product_id=self.product.id, movement_type='sale').first()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.quantity_change, Decimal('-3.000'))

    def test_insufficient_payment_fails_transaction(self):
        """Failed/underpaid transactions must reject and not deduct inventory."""
        initial_stock = self.product.stock_quantity
        cart_items = [{
            'product_id': self.product.id,
            'quantity': 1,
            'discount_amount': 0,
            'discount_percentage': 0
        }]
        # Underpayment test
        payment_data = [{
            'method': 'cash',
            'amount': '50.00'  # Less than total
        }]

        with self.assertRaises(ValueError):
            complete_sale(
                cart_items=cart_items,
                payment_data=payment_data,
                store=self.store,
                cashier=self.cashier,
                counter=self.counter
            )

        # Stock must remain unchanged
        reloaded_prod = Product.query.get(self.product.id)
        self.assertEqual(reloaded_prod.stock_quantity, initial_stock)

    def test_stock_in_and_adjustment(self):
        """Test inventory manual adjustments."""
        p = stock_in(self.product.id, 20, self.store.id, self.cashier.id, notes='Shipment 101')
        self.assertEqual(p.stock_quantity, Decimal('70.000'))

        p2 = stock_adjustment(self.product.id, 65, self.store.id, self.cashier.id, reason='Audited count')
        self.assertEqual(p2.stock_quantity, Decimal('65.000'))

        p3 = record_damaged(self.product.id, 2, self.store.id, self.cashier.id, notes='Broken seal')
        self.assertEqual(p3.stock_quantity, Decimal('63.000'))


if __name__ == '__main__':
    unittest.main()

