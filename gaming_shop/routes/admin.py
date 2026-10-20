from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from database import get_db
from security import sanitize, validate_csrf, log_audit, admin_required

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin')
@login_required
@admin_required
def admin():
    tab = sanitize(request.args.get('tab', 'orders'), 20)
    conn = get_db()

    products = conn.execute(
        'SELECT p.*, c.name as category_name FROM products p '
        'JOIN categories c ON p.category_id = c.id ORDER BY p.id'
    ).fetchall()
    orders = conn.execute('''
        SELECT o.*, u.username FROM orders o JOIN users u ON o.user_id = u.id
        ORDER BY o.created_at DESC LIMIT 50
    ''').fetchall()
    users = conn.execute(
        'SELECT id, username, email, is_admin, is_active, failed_logins, '
        'locked_until, created_at FROM users ORDER BY id'
    ).fetchall()

    audit_filter = sanitize(request.args.get('audit_filter', ''), 50)
    audit_q = '''SELECT a.*, u.username FROM audit_log a
                 LEFT JOIN users u ON a.user_id = u.id WHERE 1=1'''
    audit_params = []
    if audit_filter:
        audit_q += ' AND (a.action LIKE ? OR a.details LIKE ? OR a.ip_address LIKE ?)'
        audit_params.extend([f'%{audit_filter}%'] * 3)
    audit_q += ' ORDER BY a.created_at DESC LIMIT 100'
    audit_logs = conn.execute(audit_q, audit_params).fetchall()

    security = {
        'failed_logins_24h': conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action='login_fail' "
            "AND created_at > datetime('now', '-1 day')"
        ).fetchone()[0],
        'locked_users': conn.execute(
            "SELECT COUNT(*) FROM users WHERE locked_until IS NOT NULL "
            "AND locked_until > datetime('now')"
        ).fetchone()[0],
        'inactive_users': conn.execute(
            'SELECT COUNT(*) FROM users WHERE is_active = 0'
        ).fetchone()[0],
        'csrf_fails': conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action='csrf_fail' "
            "AND created_at > datetime('now', '-1 day')"
        ).fetchone()[0],
        'admin_denies': conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action='admin_access_denied' "
            "AND created_at > datetime('now', '-7 day')"
        ).fetchone()[0],
    }

    stats = {
        'products': conn.execute('SELECT COUNT(*) FROM products').fetchone()[0],
        'users': conn.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'orders': conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0],
        'revenue': conn.execute('SELECT COALESCE(SUM(total), 0) FROM orders').fetchone()[0],
        'reviews': conn.execute('SELECT COUNT(*) FROM reviews').fetchone()[0],
        'low_stock': conn.execute('SELECT COUNT(*) FROM products WHERE stock < 10').fetchone()[0],
    }

    reviews = conn.execute('''
        SELECT r.*, u.username, p.name as product_name FROM reviews r
        JOIN users u ON r.user_id = u.id JOIN products p ON r.product_id = p.id
        ORDER BY r.created_at DESC LIMIT 30
    ''').fetchall()

    categories = conn.execute('SELECT * FROM categories').fetchall()
    conn.close()

    return render_template(
        'admin.html', products=products, orders=orders, users=users,
        audit_logs=audit_logs, stats=stats, security=security,
        reviews=reviews, categories=categories, tab=tab,
        audit_filter=audit_filter,
    )


@admin_bp.route('/admin/order/<int:order_id>/status', methods=['POST'])
@login_required
@admin_required
def update_order_status(order_id):
    validate_csrf()
    status = sanitize(request.form.get('status', ''), 20)
    valid = ['pending', 'processing', 'shipped', 'delivered', 'cancelled']
    if status in valid:
        conn = get_db()
        old = conn.execute('SELECT status FROM orders WHERE id = ?', (order_id,)).fetchone()
        conn.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
        conn.commit()
        conn.close()
        log_audit(
            'order_status_change',
            f'Order #{order_id}: {old["status"] if old else "?"} → {status}',
        )
        flash('Статус заказа обновлён', 'success')
    return redirect(url_for('admin.admin', tab='orders'))


@admin_bp.route('/admin/user/<int:user_id>/toggle_active', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(user_id):
    validate_csrf()
    if user_id == current_user.id:
        flash('Нельзя деактивировать самого себя', 'danger')
        return redirect(url_for('admin.admin', tab='users'))
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if user:
        new_state = 0 if user['is_active'] else 1
        conn.execute(
            'UPDATE users SET is_active = ?, failed_logins = 0, locked_until = NULL WHERE id = ?',
            (new_state, user_id),
        )
        conn.commit()
        action = 'user_activated' if new_state else 'user_deactivated'
        log_audit(action, f'User: {user["username"]} (id={user_id})', severity='warning')
        flash(f'Пользователь {"активирован" if new_state else "деактивирован"}', 'success')
    conn.close()
    return redirect(url_for('admin.admin', tab='users'))


@admin_bp.route('/admin/user/<int:user_id>/toggle_admin', methods=['POST'])
@login_required
@admin_required
def toggle_user_admin(user_id):
    validate_csrf()
    if user_id == current_user.id:
        flash('Нельзя снять права с самого себя', 'danger')
        return redirect(url_for('admin.admin', tab='users'))
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if user:
        new_state = 0 if user['is_admin'] else 1
        conn.execute('UPDATE users SET is_admin = ? WHERE id = ?', (new_state, user_id))
        conn.commit()
        log_audit(
            'user_admin_toggle',
            f'User: {user["username"]} admin={new_state}',
            severity='warning',
        )
        flash(f'Права администратора {"выданы" if new_state else "сняты"}', 'success')
    conn.close()
    return redirect(url_for('admin.admin', tab='users'))


@admin_bp.route('/admin/user/<int:user_id>/unlock', methods=['POST'])
@login_required
@admin_required
def unlock_user(user_id):
    validate_csrf()
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if user:
        conn.execute(
            'UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = ?',
            (user_id,),
        )
        conn.commit()
        log_audit('user_unlocked', f'User: {user["username"]}')
        flash('Пользователь разблокирован', 'success')
    conn.close()
    return redirect(url_for('admin.admin', tab='users'))


@admin_bp.route('/admin/product/<int:product_id>/update', methods=['POST'])
@login_required
@admin_required
def update_product(product_id):
    validate_csrf()
    try:
        price = float(request.form.get('price', 0))
        stock = int(request.form.get('stock', 0))
    except (ValueError, TypeError):
        flash('Некорректные данные', 'danger')
        return redirect(url_for('admin.admin', tab='products'))
    if price < 0 or stock < 0:
        flash('Цена и склад не могут быть отрицательными', 'danger')
        return redirect(url_for('admin.admin', tab='products'))

    conn = get_db()
    old = conn.execute(
        'SELECT name, price, stock FROM products WHERE id = ?', (product_id,),
    ).fetchone()
    if old:
        conn.execute(
            'UPDATE products SET price = ?, stock = ? WHERE id = ?',
            (price, stock, product_id),
        )
        conn.commit()
        log_audit(
            'product_update',
            f'{old["name"]}: price {old["price"]}→{price}, stock {old["stock"]}→{stock}',
        )
        flash('Товар обновлён', 'success')
    conn.close()
    return redirect(url_for('admin.admin', tab='products'))


@admin_bp.route('/admin/review/<int:review_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_review(review_id):
    validate_csrf()
    conn = get_db()
    review = conn.execute('SELECT * FROM reviews WHERE id = ?', (review_id,)).fetchone()
    if review:
        product_id = review['product_id']
        conn.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
        avg = conn.execute(
            'SELECT AVG(rating) FROM reviews WHERE product_id = ?', (product_id,),
        ).fetchone()[0]
        conn.execute(
            'UPDATE products SET rating = ? WHERE id = ?',
            (round(avg, 1) if avg else 4.5, product_id),
        )
        conn.commit()
        log_audit(
            'review_deleted',
            f'Review #{review_id}, product #{product_id}',
            severity='warning',
        )
        flash('Отзыв удалён', 'success')
    conn.close()
    return redirect(url_for('admin.admin', tab='reviews'))


@admin_bp.route('/admin/audit/clear', methods=['POST'])
@login_required
@admin_required
def clear_old_audit():
    validate_csrf()
    conn = get_db()
    conn.execute("DELETE FROM audit_log WHERE created_at < datetime('now', '-30 day')")
    deleted = conn.execute('SELECT changes()').fetchone()[0]
    conn.commit()
    conn.close()
    log_audit('audit_cleared', f'Deleted {deleted} old entries', severity='warning')
    flash(f'Удалено {deleted} старых записей аудита (>30 дней)', 'success')
    return redirect(url_for('admin.admin', tab='audit'))
