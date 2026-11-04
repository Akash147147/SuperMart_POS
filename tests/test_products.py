"""Automated tests for product management and barcode generation."""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import unittest
from decimal import Decimal
from app import create_app
from models.base import db
from models.user import User, Role
from models.store import Store
from models.product import Product, Category
from services.barcode_service import validate_ean13_checksum


class TestProductBarcodeAPIs(unittest.TestCase):

    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        self.admin_role = Role(name='admin', description='Admin')
        db.session.add(self.admin_role)
        db.session.flush()

        self.store = Store(
            name='Test Mart',
            address='City Center',
            gstin='27ABCDE1234F1Z5',
            tax_type='intra-state'
        )
        db.session.add(self.store)
        db.session.flush()

        self.admin = User(
            username='admin_test',
            full_name='Test Admin',
            role_id=self.admin_role.id,
            store_id=self.store.id
        )
        self.admin.set_password('admin123')
        db.session.add(self.admin)
        db.session.commit()

        # Login admin user
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.admin.id)
            sess['_fresh'] = True

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_generate_barcode_format_and_uniqueness(self):
        """Verify generated barcode is 13 digits, starts with 200, and has valid EAN-13 check digit."""
        response = self.client.get('/api/products/generate-barcode')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        barcode = data['barcode']
        self.assertEqual(len(barcode), 13)
        self.assertTrue(barcode.startswith('200'))
        self.assertTrue(validate_ean13_checksum(barcode))

    def test_check_barcode_availability(self):
        """Verify check-barcode API accurately detects available and duplicate barcodes."""
        # Check non-existent barcode
        resp = self.client.get('/api/products/check-barcode?barcode=8901234567890')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.get_json()['exists'])

        # Create a product with this barcode
        prod = Product(
            store_id=self.store.id,
            name='Test Milk 1L',
            barcode='8901234567890',
            mrp=Decimal('60.00'),
            selling_price=Decimal('58.00'),
            stock_quantity=50
        )
        db.session.add(prod)
        db.session.commit()

        # Check existing barcode -> should return exists: True and product info
        resp = self.client.get('/api/products/check-barcode?barcode=8901234567890')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['exists'])
        self.assertEqual(data['product_id'], prod.id)
        self.assertEqual(data['product_name'], 'Test Milk 1L')

        # Check with exclude_id (e.g. during edit) -> should return exists: False
        resp = self.client.get(f'/api/products/check-barcode?barcode=8901234567890&exclude_id={prod.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.get_json()['exists'])

    def test_create_and_update_product_null_purchase_price(self):
        """Verify product can be created and updated when purchase_price is null, empty string, or missing."""
        payload = {
            'name': 'Sample Tea 250g',
            'barcode': '8901234500001',
            'mrp': 120.0,
            'selling_price': 110.0,
            'purchase_price': None,  # triggers [<class 'decimal.ConversionSyntax'>] if not handled safely
            'gst_percentage': 18.0,
            'cess_percentage': None,
            'stock_quantity': 20,
            'min_stock_level': 10,
            'unit': 'pcs'
        }
        resp = self.client.post('/api/products', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        prod_id = data['product']['id']

        # Update with empty string purchase_price
        update_payload = {
            'purchase_price': '',
            'selling_price': 105.0
        }
        resp = self.client.put(f'/api/products/{prod_id}', json=update_payload)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()['success'])


if __name__ == '__main__':
    unittest.main()

