"""GameGear application factory.

Usage
-----
Development::

    python app.py

Production (example)::

    export SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
    export SESSION_COOKIE_SECURE=1
    export ENABLE_HSTS=1
    gunicorn -w 4 -b 0.0.0.0:8000 'app:create_app()'
"""
from flask import Flask, flash, redirect, url_for
from flask_login import current_user

from config import Config
from extensions import login_manager
from database import get_db, init_db
from security import generate_csrf_token, set_security_headers
import models  # noqa: F401 — registers user_loader


def create_app(config_class=Config):
    """Build and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    login_manager.init_app(app)

    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.cart import cart_bp
    from routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(admin_bp)

    @app.after_request
    def _security_headers(response):
        return set_security_headers(response)

    @app.context_processor
    def inject_globals():
        data = {'csrf_token': generate_csrf_token, 'cart_count': 0}
        if current_user.is_authenticated:
            try:
                conn = get_db()
                count = conn.execute(
                    'SELECT COALESCE(SUM(quantity), 0) FROM cart WHERE user_id = ?',
                    (current_user.id,),
                ).fetchone()[0]
                conn.close()
                data['cart_count'] = count
            except Exception:
                pass
        return data

    @app.errorhandler(403)
    def forbidden(e):
        flash('Доступ запрещён (CSRF или права)', 'danger')
        return redirect(url_for('main.index'))

    @app.errorhandler(404)
    def not_found(e):
        return 'Страница не найдена', 404

    @app.errorhandler(500)
    def server_error(e):
        return 'Внутренняя ошибка сервера', 500

    return app


app = create_app()

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
