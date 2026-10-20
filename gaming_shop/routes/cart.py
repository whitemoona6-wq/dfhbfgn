import re

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from database import get_db
from security import sanitize, validate_csrf, log_audit

cart_bp = Blueprint('cart', __name__)


@cart_bp.route('/cart')
@login_required
def cart():
    conn = get_db()
    items = conn.execute('''
        SELECT c.id as cart_id, c.quantity, p.*, (c.quantity * p.price) as subtotal
        FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id = ?
    ''', (current_user.id,)).fetchall()
    total = sum(item['subtotal'] for item in items)
    conn.close()
    return render_template('cart.html', items=items, total=total)


@cart_bp.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    validate_csrf()
    try:
        quantity = int(request.form.get('quantity', 1))
    except (ValueError, TypeError):
        quantity = 1
    quantity = max(1, min(quantity, 99))

    conn = get_db()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        flash('Товар не найден', 'danger')
        conn.close()
        return redirect(url_for('main.catalog'))
    if product['stock'] < quantity:
        flash('Недостаточно товара на складе', 'warning')
        conn.close()
        return redirect(url_for('main.product_detail', product_id=product_id))

    existing = conn.execute(
        'SELECT * FROM cart WHERE user_id = ? AND product_id = ?',
        (current_user.id, product_id),
    ).fetchone()
    if existing:
        new_qty = existing['quantity'] + quantity
        if new_qty > product['stock']:
            flash('Недостаточно товара на складе', 'warning')
        else:
            conn.execute('UPDATE cart SET quantity = ? WHERE id = ?', (new_qty, existing['id']))
            conn.commit()
            flash('Количество товара в корзине обновлено', 'success')
    else:
        conn.execute(
            'INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)',
            (current_user.id, product_id, quantity),
        )
        conn.commit()
        flash('Товар добавлен в корзину', 'success')
    conn.close()
    return redirect(request.referrer or url_for('main.catalog'))


@cart_bp.route('/cart/update/<int:cart_id>', methods=['POST'])
@login_required
def update_cart(cart_id):
    validate_csrf()
    try:
        quantity = int(request.form.get('quantity', 1))
    except (ValueError, TypeError):
        quantity = 1

    conn = get_db()
    item = conn.execute(
        'SELECT c.*, p.stock FROM cart c JOIN products p ON c.product_id = p.id '
        'WHERE c.id = ? AND c.user_id = ?',
        (cart_id, current_user.id),
    ).fetchone()
    if not item:
        flash('Товар не найден в корзине', 'danger')
        conn.close()
        return redirect(url_for('cart.cart'))
    if quantity <= 0:
        conn.execute('DELETE FROM cart WHERE id = ?', (cart_id,))
        flash('Товар удалён из корзины', 'info')
    elif quantity > item['stock']:
        flash('Недостаточно товара на складе', 'warning')
    else:
        conn.execute('UPDATE cart SET quantity = ? WHERE id = ?', (quantity, cart_id))
        flash('Корзина обновлена', 'success')
    conn.commit()
    conn.close()
    return redirect(url_for('cart.cart'))


@cart_bp.route('/cart/remove/<int:cart_id>', methods=['POST'])
@login_required
def remove_from_cart(cart_id):
    validate_csrf()
    conn = get_db()
    conn.execute('DELETE FROM cart WHERE id = ? AND user_id = ?', (cart_id, current_user.id))
    conn.commit()
    conn.close()
    flash('Товар удалён из корзины', 'info')
    return redirect(url_for('cart.cart'))


@cart_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    conn = get_db()
    items = conn.execute('''
        SELECT c.quantity, p.*, (c.quantity * p.price) as subtotal
        FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id = ?
    ''', (current_user.id,)).fetchall()
    if not items:
        flash('Корзина пуста', 'warning')
        conn.close()
        return redirect(url_for('cart.cart'))
    total = sum(item['subtotal'] for item in items)

    if request.method == 'POST':
        validate_csrf()
        address = sanitize(request.form.get('address', ''), 300)
        phone = sanitize(request.form.get('phone', ''), 30)
        if not address or not phone:
            flash('Заполните адрес и телефон', 'danger')
            conn.close()
            return render_template('checkout.html', items=items, total=total)
        if not re.match(r'^[\d\s\+\-\(\)]{7,20}$', phone):
            flash('Некорректный номер телефона', 'danger')
            conn.close()
            return render_template('checkout.html', items=items, total=total)

        for item in items:
            if item['quantity'] > item['stock']:
                flash(f'Недостаточно товара: {item["name"]}', 'danger')
                conn.close()
                return redirect(url_for('cart.cart'))

        cursor = conn.execute(
            'INSERT INTO orders (user_id, total, address, phone, status) VALUES (?, ?, ?, ?, ?)',
            (current_user.id, total, address, phone, 'processing'),
        )
        order_id = cursor.lastrowid
        for item in items:
            conn.execute(
                'INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)',
                (order_id, item['id'], item['quantity'], item['price']),
            )
            conn.execute(
                'UPDATE products SET stock = stock - ? WHERE id = ?',
                (item['quantity'], item['id']),
            )
        conn.execute('DELETE FROM cart WHERE user_id = ?', (current_user.id,))
        conn.commit()
        conn.close()
        log_audit('order_created', f'Order #{order_id}, total={total}', severity='info')
        flash(f'Заказ №{order_id} успешно оформлен! Сумма: {total:,.0f} ₽', 'success')
        return redirect(url_for('cart.orders'))

    conn.close()
    return render_template('checkout.html', items=items, total=total)


@cart_bp.route('/orders')
@login_required
def orders():
    conn = get_db()
    user_orders = conn.execute(
        'SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC',
        (current_user.id,),
    ).fetchall()
    orders_with_items = []
    for order in user_orders:
        items = conn.execute('''
            SELECT oi.*, p.name, p.image_url FROM order_items oi
            JOIN products p ON oi.product_id = p.id WHERE oi.order_id = ?
        ''', (order['id'],)).fetchall()
        orders_with_items.append({'order': order, 'items': items})
    conn.close()
    return render_template('orders.html', orders=orders_with_items)


@cart_bp.route('/review/<int:product_id>', methods=['POST'])
@login_required
def add_review(product_id):
    validate_csrf()
    try:
        rating = int(request.form.get('rating', 5))
    except (ValueError, TypeError):
        rating = 5
    comment = sanitize(request.form.get('comment', ''), 1000)
    if rating < 1 or rating > 5:
        flash('Оценка от 1 до 5', 'danger')
        return redirect(url_for('main.product_detail', product_id=product_id))

    conn = get_db()
    existing = conn.execute(
        'SELECT id FROM reviews WHERE product_id = ? AND user_id = ?',
        (product_id, current_user.id),
    ).fetchone()
    if existing:
        flash('Вы уже оставляли отзыв на этот товар', 'warning')
        conn.close()
        return redirect(url_for('main.product_detail', product_id=product_id))

    conn.execute(
        'INSERT INTO reviews (product_id, user_id, rating, comment) VALUES (?, ?, ?, ?)',
        (product_id, current_user.id, rating, comment),
    )
    avg = conn.execute(
        'SELECT AVG(rating) FROM reviews WHERE product_id = ?', (product_id,),
    ).fetchone()[0]
    conn.execute('UPDATE products SET rating = ? WHERE id = ?', (round(avg, 1), product_id))
    conn.commit()
    conn.close()
    log_audit('review_added', f'Product #{product_id}, rating={rating}')
    flash('Отзыв добавлен!', 'success')
    return redirect(url_for('main.product_detail', product_id=product_id))


@cart_bp.route('/profile')
@login_required
def profile():
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (current_user.id,)).fetchone()
    order_count = conn.execute(
        'SELECT COUNT(*) FROM orders WHERE user_id = ?', (current_user.id,),
    ).fetchone()[0]
    cart_count = conn.execute(
        'SELECT COUNT(*) FROM cart WHERE user_id = ?', (current_user.id,),
    ).fetchone()[0]
    conn.close()
    return render_template('profile.html', user=user, order_count=order_count, cart_count=cart_count)
