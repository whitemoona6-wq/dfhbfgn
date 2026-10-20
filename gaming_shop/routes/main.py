from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import get_db
from security import sanitize

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    conn = get_db()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    products = conn.execute('''
        SELECT p.*, c.name as category_name, c.slug as category_slug
        FROM products p JOIN categories c ON p.category_id = c.id
        ORDER BY p.rating DESC LIMIT 8
    ''').fetchall()
    conn.close()
    return render_template('index.html', products=products, categories=categories)


@main_bp.route('/catalog')
def catalog():
    conn = get_db()
    category_slug = sanitize(request.args.get('category', ''), 50)
    search = sanitize(request.args.get('q', ''), 100)
    sort = sanitize(request.args.get('sort', 'rating'), 20)
    brand = sanitize(request.args.get('brand', ''), 50)

    query = '''SELECT p.*, c.name as category_name, c.slug as category_slug
               FROM products p JOIN categories c ON p.category_id = c.id WHERE 1=1'''
    params = []

    if category_slug:
        query += ' AND c.slug = ?'
        params.append(category_slug)
    if search:
        query += ' AND (p.name LIKE ? OR p.description LIKE ? OR p.brand LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    if brand:
        query += ' AND p.brand = ?'
        params.append(brand)

    sort_map = {
        'price_asc': ' ORDER BY p.price ASC',
        'price_desc': ' ORDER BY p.price DESC',
        'name': ' ORDER BY p.name ASC',
    }
    query += sort_map.get(sort, ' ORDER BY p.rating DESC')

    products = conn.execute(query, params).fetchall()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    brands = conn.execute('SELECT DISTINCT brand FROM products ORDER BY brand').fetchall()
    conn.close()
    return render_template(
        'catalog.html', products=products, categories=categories,
        brands=brands, current_category=category_slug,
        search=search, sort=sort, current_brand=brand,
    )


@main_bp.route('/product/<int:product_id>')
def product_detail(product_id):
    conn = get_db()
    product = conn.execute('''
        SELECT p.*, c.name as category_name, c.slug as category_slug
        FROM products p JOIN categories c ON p.category_id = c.id WHERE p.id = ?
    ''', (product_id,)).fetchone()
    if not product:
        flash('Товар не найден', 'danger')
        conn.close()
        return redirect(url_for('main.catalog'))
    reviews = conn.execute('''
        SELECT r.*, u.username FROM reviews r JOIN users u ON r.user_id = u.id
        WHERE r.product_id = ? ORDER BY r.created_at DESC
    ''', (product_id,)).fetchall()
    related = conn.execute(
        'SELECT * FROM products WHERE category_id = ? AND id != ? LIMIT 4',
        (product['category_id'], product_id),
    ).fetchall()
    conn.close()
    return render_template('product.html', product=product, reviews=reviews, related=related)
