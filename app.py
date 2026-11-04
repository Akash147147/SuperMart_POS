"""SuperMart POS - Flask Application Factory."""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Ensure project base directory is always in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from config import config_map
from models.base import db
from models.user import User


login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()


def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config_map.get(config_name, config_map['development']))

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # Login manager config
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access the POS system.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.products import products_bp
    from routes.billing import billing_bp
    from routes.inventory import inventory_bp
    from routes.sales import sales_bp
    from routes.reports import reports_bp
    from routes.settings import settings_bp
    from routes.hardware import hardware_bp
    from routes.customers import customers_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(hardware_bp)
    app.register_blueprint(customers_bp)

    # Context processors
    @app.context_processor
    def inject_globals():
        return {
            'now': datetime.now(timezone.utc),
            'app_name': 'SuperMart POS',
        }

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return {'success': False, 'message': 'Not found'}, 404

    @app.errorhandler(500)
    def server_error(e):
        return {'success': False, 'message': 'Internal server error'}, 500

    return app


def init_database(app):
    """Initialize database with default data."""
    with app.app_context():
        db.create_all()

        from models.user import Role
        from models.store import Store, BillingCounter

        # Create roles if not exist
        if not Role.query.filter_by(name='admin').first():
            admin_role = Role(name='admin', description='Administrator / Owner')
            cashier_role = Role(name='cashier', description='Cashier')
            db.session.add_all([admin_role, cashier_role])
            db.session.flush()

            # Create default store
            store = Store(
                name='SuperMart',
                address='123 Main Street',
                city='Mumbai',
                state='Maharashtra',
                state_code='27',
                phone='9876543210',
                currency='INR',
                tax_type='intra-state',
                receipt_footer='Thank You! Visit Again!',
            )
            db.session.add(store)
            db.session.flush()

            # Create default counter
            counter = BillingCounter(store_id=store.id, name='Counter 1')
            db.session.add(counter)
            db.session.flush()

            # Create default admin user
            admin = User(
                username='admin',
                full_name='Administrator',
                role_id=admin_role.id,
                store_id=store.id,
            )
            admin.set_password('admin123')
            db.session.add(admin)

            # Create default cashier
            cashier = User(
                username='cashier',
                full_name='Cashier 1',
                role_id=cashier_role.id,
                store_id=store.id,
            )
            cashier.set_password('cashier123')
            db.session.add(cashier)

            # Create default categories
            from models.product import Category
            categories = ['Groceries', 'Dairy', 'Beverages', 'Snacks', 'Personal Care',
                          'Household', 'Fruits & Vegetables', 'Frozen Foods', 'Bakery', 'Others']
            for cat_name in categories:
                cat = Category(store_id=store.id, name=cat_name)
                db.session.add(cat)

            # Create sample products
            from models.product import Product
            from decimal import Decimal
            sample_products = [
                {'name': 'Basmati Rice 1KG', 'barcode': '8901234567890', 'hsn_code': '1006',
                 'category': 'Groceries', 'brand': 'India Gate', 'size_weight': '1KG', 'unit': 'pcs',
                 'mrp': '120.00', 'selling_price': '110.00', 'purchase_price': '90.00',
                 'gst_percentage': '5.00', 'stock_quantity': '100'},
                {'name': 'Amul Taza Milk 500ML', 'barcode': '8901234567891', 'hsn_code': '0401',
                 'category': 'Dairy', 'brand': 'Amul', 'size_weight': '500ML', 'unit': 'pcs',
                 'mrp': '30.00', 'selling_price': '28.00', 'purchase_price': '24.00',
                 'gst_percentage': '0.00', 'stock_quantity': '200'},
                {'name': 'Britannia Bread', 'barcode': '8901234567892', 'hsn_code': '1905',
                 'category': 'Bakery', 'brand': 'Britannia', 'size_weight': '400g', 'unit': 'pcs',
                 'mrp': '45.00', 'selling_price': '42.00', 'purchase_price': '35.00',
                 'gst_percentage': '5.00', 'stock_quantity': '50'},
                {'name': 'Coca-Cola 750ML', 'barcode': '8901234567893', 'hsn_code': '2202',
                 'category': 'Beverages', 'brand': 'Coca-Cola', 'size_weight': '750ML', 'unit': 'pcs',
                 'mrp': '40.00', 'selling_price': '40.00', 'purchase_price': '32.00',
                 'gst_percentage': '28.00', 'stock_quantity': '150'},
                {'name': 'Maggi Noodles', 'barcode': '8901234567894', 'hsn_code': '1902',
                 'category': 'Snacks', 'brand': 'Nestle', 'size_weight': '70g', 'unit': 'pcs',
                 'mrp': '14.00', 'selling_price': '12.00', 'purchase_price': '10.00',
                 'gst_percentage': '18.00', 'stock_quantity': '300'},
                {'name': 'Surf Excel Detergent 1KG', 'barcode': '8901234567895', 'hsn_code': '3402',
                 'category': 'Household', 'brand': 'Surf Excel', 'size_weight': '1KG', 'unit': 'pcs',
                 'mrp': '200.00', 'selling_price': '185.00', 'purchase_price': '160.00',
                 'gst_percentage': '18.00', 'stock_quantity': '75'},
                {'name': 'Dettol Soap 125g', 'barcode': '8901234567896', 'hsn_code': '3401',
                 'category': 'Personal Care', 'brand': 'Dettol', 'size_weight': '125g', 'unit': 'pcs',
                 'mrp': '55.00', 'selling_price': '50.00', 'purchase_price': '40.00',
                 'gst_percentage': '18.00', 'stock_quantity': '120'},
                {'name': 'Aashirvaad Atta 5KG', 'barcode': '8901234567897', 'hsn_code': '1101',
                 'category': 'Groceries', 'brand': 'Aashirvaad', 'size_weight': '5KG', 'unit': 'pcs',
                 'mrp': '300.00', 'selling_price': '280.00', 'purchase_price': '240.00',
                 'gst_percentage': '5.00', 'stock_quantity': '60'},
                {'name': 'Tomato 1KG', 'barcode': '', 'hsn_code': '0702',
                 'category': 'Fruits & Vegetables', 'brand': '', 'size_weight': '1KG', 'unit': 'kg',
                 'mrp': '40.00', 'selling_price': '40.00', 'purchase_price': '30.00',
                 'gst_percentage': '0.00', 'stock_quantity': '50', 'sold_by_weight': True},
                {'name': 'Sugar 1KG', 'barcode': '8901234567898', 'hsn_code': '1701',
                 'category': 'Groceries', 'brand': 'Local', 'size_weight': '1KG', 'unit': 'pcs',
                 'mrp': '50.00', 'selling_price': '45.00', 'purchase_price': '38.00',
                 'gst_percentage': '5.00', 'stock_quantity': '200'},
            ]

            for sp in sample_products:
                cat = Category.query.filter_by(store_id=store.id, name=sp['category']).first()
                product = Product(
                    store_id=store.id,
                    name=sp['name'],
                    barcode=sp['barcode'] if sp['barcode'] else None,
                    hsn_code=sp['hsn_code'],
                    category_id=cat.id if cat else None,
                    brand=sp.get('brand', ''),
                    size_weight=sp.get('size_weight', ''),
                    unit=sp.get('unit', 'pcs'),
                    mrp=Decimal(sp['mrp']),
                    selling_price=Decimal(sp['selling_price']),
                    purchase_price=Decimal(sp['purchase_price']),
                    gst_percentage=Decimal(sp['gst_percentage']),
                    stock_quantity=Decimal(sp['stock_quantity']),
                    min_stock_level=Decimal('10'),
                    sold_by_weight=sp.get('sold_by_weight', False),
                )
                db.session.add(product)

            db.session.commit()
            print("[OK] Database initialized with default data")
            print("  Admin: admin / admin123")
            print("  Cashier: cashier / cashier123")
        else:
            print("[OK] Database already initialized")


# Application entry point
app = create_app()

if __name__ == '__main__':
    init_database(app)
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    app.run(host=host, port=port, debug=True)

