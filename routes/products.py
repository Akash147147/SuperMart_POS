"""Product routes and management APIs."""
import csv
import io
from decimal import Decimal
from functools import wraps
from flask import Blueprint, request, jsonify, render_template, Response
from flask_login import login_required, current_user
from models.base import db
from models.product import Product, Category

products_bp = Blueprint('products', __name__)


def to_decimal(val, default='0.00'):
    """Safely convert a value to Decimal, returning default if None, empty, or invalid."""
    if val is None or val == '' or val == 'null':
        return Decimal(str(default))
    try:
        if isinstance(val, str):
            val = val.strip()
            if not val or val.lower() in ('none', 'null', 'nan'):
                return Decimal(str(default))
        return Decimal(str(val))
    except Exception:
        return Decimal(str(default))


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({'success': False, 'message': 'Admin privilege required'}), 403
        return f(*args, **kwargs)
    return decorated_function


@products_bp.route('/products')
@login_required
def products_page():
    return render_template('products.html')


@products_bp.route('/api/categories', methods=['GET'])
@login_required
def get_categories():
    store_id = current_user.store_id or 1
    categories = Category.query.filter_by(store_id=store_id, is_active=True).all()
    return jsonify({
        'success': True,
        'categories': [{'id': c.id, 'name': c.name, 'description': c.description} for c in categories]
    })


@products_bp.route('/api/categories', methods=['POST'])
@login_required
@admin_required
def create_category():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Category name required'}), 400
    store_id = current_user.store_id or 1
    existing = Category.query.filter_by(store_id=store_id, name=name).first()
    if existing:
        return jsonify({'success': False, 'message': 'Category already exists'}), 400
    category = Category(
        store_id=store_id,
        name=name,
        description=data.get('description', '')
    )
    db.session.add(category)
    db.session.commit()
    return jsonify({'success': True, 'category': {'id': category.id, 'name': category.name}})


@products_bp.route('/api/products', methods=['GET'])
@login_required
def list_products():
    store_id = current_user.store_id or 1
    query = Product.query.filter_by(store_id=store_id)

    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            db.or_(
                Product.name.ilike(f'%{search}%'),
                Product.barcode.ilike(f'%{search}%'),
                Product.brand.ilike(f'%{search}%'),
                Product.hsn_code.ilike(f'%{search}%')
            )
        )

    category_param = request.args.get('category_id') or request.args.get('category')
    if category_param:
        try:
            cid = int(category_param)
            query = query.filter_by(category_id=cid)
        except (ValueError, TypeError):
            cat = Category.query.filter_by(store_id=store_id, name=category_param).first()
            if cat:
                query = query.filter_by(category_id=cat.id)

    status_filter = request.args.get('status')
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    elif status_filter == 'low_stock':
        query = query.filter(Product.is_active == True, Product.stock_quantity <= Product.min_stock_level)
    elif status_filter == 'out_of_stock':
        query = query.filter(Product.is_active == True, Product.stock_quantity <= 0)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    pagination = query.order_by(Product.name.asc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'success': True,
        'products': [p.to_dict() for p in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'total_pages': pagination.pages,
        'current_page': pagination.page
    })


@products_bp.route('/api/products/check-barcode', methods=['GET'])
@login_required
def check_barcode():
    store_id = current_user.store_id or 1
    barcode = request.args.get('barcode', '').strip()
    exclude_id = request.args.get('exclude_id', type=int)
    if not barcode:
        return jsonify({'exists': False})

    query = Product.query.filter_by(store_id=store_id, barcode=barcode)
    if exclude_id:
        query = query.filter(Product.id != exclude_id)

    existing = query.first()
    if existing:
        return jsonify({'exists': True, 'product_id': existing.id, 'product_name': existing.name})
    return jsonify({'exists': False})


@products_bp.route('/api/products/generate-barcode', methods=['GET'])
@login_required
def generate_barcode():
    """Generate a unique valid EAN-13 barcode with internal prefix 200."""
    import random
    store_id = current_user.store_id or 1
    for _ in range(50):
        # 200 prefix + 9 random digits
        base = "200" + "".join(str(random.randint(0, 9)) for _ in range(9))
        total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(base))
        check = (10 - (total % 10)) % 10
        barcode = base + str(check)
        if not Product.query.filter_by(store_id=store_id, barcode=barcode).first():
            return jsonify({'success': True, 'barcode': barcode})
    return jsonify({'success': False, 'message': 'Could not generate unique barcode'}), 500


@products_bp.route('/api/products/<int:id>/status', methods=['PUT'])
@login_required
@admin_required
def update_product_status(id):
    product = Product.query.get_or_404(id)
    data = request.get_json() or {}
    if 'is_active' in data:
        product.is_active = bool(data['is_active'])
        db.session.commit()
        return jsonify({'success': True, 'message': 'Product status updated', 'product': product.to_dict()})
    return jsonify({'success': False, 'message': 'is_active field required'}), 400


@products_bp.route('/api/products/<int:id>', methods=['GET'])
@login_required
def get_product(id):
    product = Product.query.get_or_404(id)
    return jsonify({'success': True, 'product': product.to_dict()})


@products_bp.route('/api/products', methods=['POST'])
@login_required
@admin_required
def create_product():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Product name is required'}), 400

    store_id = current_user.store_id or 1
    barcode = (data.get('barcode') or '').strip() or None
    if barcode:
        dup = Product.query.filter_by(store_id=store_id, barcode=barcode).first()
        if dup:
            return jsonify({'success': False, 'message': f'Barcode {barcode} is already used'}), 400

    try:
        product = Product(
            store_id=store_id,
            name=name,
            barcode=barcode,
            hsn_code=data.get('hsn_code'),
            category_id=data.get('category_id') or None,
            brand=data.get('brand'),
            size_weight=data.get('size_weight'),
            unit=data.get('unit', 'pcs'),
            mrp=to_decimal(data.get('mrp'), '0.00'),
            selling_price=to_decimal(data.get('selling_price'), '0.00'),
            purchase_price=to_decimal(data.get('purchase_price'), '0.00'),
            gst_percentage=to_decimal(data.get('gst_percentage'), '0.00'),
            cess_percentage=to_decimal(data.get('cess_percentage'), '0.00'),
            is_gst_exempt=bool(data.get('is_gst_exempt', False)),
            stock_quantity=to_decimal(data.get('stock_quantity'), '0.000'),
            min_stock_level=to_decimal(data.get('min_stock_level'), '5.000'),
            sold_by_weight=bool(data.get('sold_by_weight', False)),
            is_active=bool(data.get('is_active', True))
        )
        db.session.add(product)
        db.session.commit()
        return jsonify({'success': True, 'product': product.to_dict(), 'message': 'Product created successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@products_bp.route('/api/products/<int:id>', methods=['PUT'])
@login_required
@admin_required
def update_product(id):
    product = Product.query.get_or_404(id)
    data = request.get_json() or {}

    barcode = (data.get('barcode') or '').strip() or None
    if barcode and barcode != product.barcode:
        dup = Product.query.filter(
            Product.store_id == product.store_id,
            Product.barcode == barcode,
            Product.id != product.id
        ).first()
        if dup:
            return jsonify({'success': False, 'message': f'Barcode {barcode} already in use'}), 400
        product.barcode = barcode
    elif barcode == '':
        product.barcode = None

    if 'name' in data:
        product.name = data['name'].strip()
    if 'hsn_code' in data:
        product.hsn_code = data['hsn_code']
    if 'category_id' in data:
        product.category_id = data['category_id'] or None
    if 'brand' in data:
        product.brand = data['brand']
    if 'size_weight' in data:
        product.size_weight = data['size_weight']
    if 'unit' in data:
        product.unit = data['unit']
    if 'mrp' in data:
        product.mrp = to_decimal(data['mrp'], product.mrp or '0.00')
    if 'selling_price' in data:
        product.selling_price = to_decimal(data['selling_price'], product.selling_price or '0.00')
    if 'purchase_price' in data:
        product.purchase_price = to_decimal(data['purchase_price'], '0.00')
    if 'gst_percentage' in data:
        product.gst_percentage = to_decimal(data['gst_percentage'], '0.00')
    if 'cess_percentage' in data:
        product.cess_percentage = to_decimal(data['cess_percentage'], '0.00')
    if 'is_gst_exempt' in data:
        product.is_gst_exempt = bool(data['is_gst_exempt'])
    if 'stock_quantity' in data:
        product.stock_quantity = to_decimal(data['stock_quantity'], product.stock_quantity or '0.000')
    if 'min_stock_level' in data:
        product.min_stock_level = to_decimal(data['min_stock_level'], product.min_stock_level or '5.000')
    if 'sold_by_weight' in data:
        product.sold_by_weight = bool(data['sold_by_weight'])
    if 'is_active' in data:
        product.is_active = bool(data['is_active'])

    db.session.commit()
    return jsonify({'success': True, 'product': product.to_dict(), 'message': 'Product updated successfully'})


@products_bp.route('/api/products/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    product.is_active = False
    db.session.commit()
    return jsonify({'success': True, 'message': 'Product deactivated'})


@products_bp.route('/api/products/barcode/<barcode>', methods=['GET'])
@login_required
def get_by_barcode(barcode):
    store_id = current_user.store_id or 1
    product = Product.query.filter_by(store_id=store_id, barcode=barcode, is_active=True).first()
    if not product:
        return jsonify({'success': False, 'message': 'Product not found'}), 404
    return jsonify({'success': True, 'product': product.to_dict()})


@products_bp.route('/api/products/export', methods=['GET'])
@login_required
def export_products():
    store_id = current_user.store_id or 1
    products = Product.query.filter_by(store_id=store_id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'ID', 'Name', 'Barcode', 'HSN Code', 'Category', 'Brand', 'Size/Weight',
        'Unit', 'MRP', 'Selling Price', 'Purchase Price', 'GST %', 'Stock', 'Min Stock', 'Active'
    ])
    for p in products:
        writer.writerow([
            p.id, p.name, p.barcode or '', p.hsn_code or '',
            p.category.name if p.category else '', p.brand or '', p.size_weight or '',
            p.unit or '', p.mrp, p.selling_price, p.purchase_price,
            p.gst_percentage, p.stock_quantity, p.min_stock_level, 'Yes' if p.is_active else 'No'
        ])
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=products.csv'}
    )


@products_bp.route('/api/products/import', methods=['POST'])
@login_required
@admin_required
def import_products():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'}), 400
    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'success': False, 'message': 'Please upload a CSV file'}), 400

    store_id = current_user.store_id or 1
    stream = io.StringIO(file.stream.read().decode('utf-8', errors='ignore'))
    reader = csv.DictReader(stream)

    imported = 0
    errors = []
    for idx, row in enumerate(reader, start=2):
        name = row.get('name') or row.get('Name')
        if not name:
            continue
        barcode = row.get('barcode') or row.get('Barcode') or None
        if barcode:
            barcode = barcode.strip()
            if Product.query.filter_by(store_id=store_id, barcode=barcode).first():
                errors.append(f"Row {idx}: Barcode {barcode} already exists")
                continue

        cat_name = row.get('category') or row.get('Category')
        cat_id = None
        if cat_name:
            cat = Category.query.filter_by(store_id=store_id, name=cat_name.strip()).first()
            if not cat:
                cat = Category(store_id=store_id, name=cat_name.strip())
                db.session.add(cat)
                db.session.flush()
            cat_id = cat.id

        try:
            p = Product(
                store_id=store_id,
                name=name.strip(),
                barcode=barcode,
                hsn_code=row.get('hsn_code') or row.get('HSN Code') or '',
                category_id=cat_id,
                brand=row.get('brand') or row.get('Brand') or '',
                size_weight=row.get('size_weight') or row.get('Size/Weight') or '',
                unit=row.get('unit') or row.get('Unit') or 'pcs',
                mrp=to_decimal(row.get('mrp') or row.get('MRP'), '0.00'),
                selling_price=to_decimal(row.get('selling_price') or row.get('Selling Price'), '0.00'),
                purchase_price=to_decimal(row.get('purchase_price') or row.get('Purchase Price'), '0.00'),
                gst_percentage=to_decimal(row.get('gst_percentage') or row.get('GST %'), '0.00'),
                stock_quantity=to_decimal(row.get('stock_quantity') or row.get('Stock'), '0.000'),
                min_stock_level=to_decimal(row.get('min_stock_level') or row.get('Min Stock'), '5.000'),
                is_active=True
            )
            db.session.add(p)
            imported += 1
        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")

    db.session.commit()
    return jsonify({
        'success': True,
        'message': f'Successfully imported {imported} products.',
        'errors': errors
    })

