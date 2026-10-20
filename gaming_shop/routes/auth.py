"""Authentication routes: register, login, logout.

Security measures applied here:
* CSRF validation on every POST
* IP rate limiting + per-account lockout
* Session fixation protection (clear session before login_user)
* CSRF token rotation after successful login
* Strong password hashing (scrypt)
* Generic error messages to avoid user enumeration on login
"""
import re
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from database import get_db
from models import User
from security import (
    _login_attempts,
    _register_attempts,
    check_rate_limit,
    get_client_ip,
    is_strong_password,
    is_valid_email,
    log_audit,
    record_attempt,
    rotate_csrf_token,
    sanitize,
    validate_csrf,
)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        validate_csrf()
        ip = get_client_ip()
        if not check_rate_limit(
            _register_attempts, ip, Config.MAX_REGISTER_ATTEMPTS, 30,
        ):
            flash('Слишком много попыток регистрации. Подождите 30 минут.', 'danger')
            log_audit('register_rate_limit', f'IP: {ip}', severity='warning')
            return render_template('register.html')

        username = sanitize(request.form.get('username', ''), 50)
        email = sanitize(request.form.get('email', ''), 120).lower()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        if not username or not email or not password:
            flash('Заполните все поля', 'danger')
            return render_template('register.html')
        if not re.match(r'^[a-zA-Z0-9_]{3,30}$', username):
            flash('Имя: 3–30 символов, только латиница, цифры и _', 'danger')
            return render_template('register.html')
        if not is_valid_email(email):
            flash('Некорректный email', 'danger')
            return render_template('register.html')
        if password != password2:
            flash('Пароли не совпадают', 'danger')
            return render_template('register.html')
        ok, msg = is_strong_password(password)
        if not ok:
            flash(msg, 'danger')
            return render_template('register.html')

        record_attempt(_register_attempts, ip)
        conn = get_db()
        try:
            password_hash = generate_password_hash(password, method='scrypt')
            conn.execute(
                'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                (username, email, password_hash),
            )
            conn.commit()
            log_audit('register', f'New user: {username}', severity='info')
            flash('Регистрация успешна! Теперь войдите.', 'success')
            return redirect(url_for('auth.login'))
        except Exception:
            flash('Пользователь с таким именем или email уже существует', 'danger')
            log_audit(
                'register_duplicate',
                f'Attempt: {username}/{email}',
                severity='info',
            )
        finally:
            conn.close()

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        validate_csrf()
        ip = get_client_ip()
        window = getattr(Config, 'LOGIN_WINDOW_MINUTES', Config.LOCKOUT_MINUTES)
        if not check_rate_limit(
            _login_attempts, ip, Config.MAX_LOGIN_ATTEMPTS, window,
        ):
            flash(
                f'Слишком много попыток входа. Подождите {Config.LOCKOUT_MINUTES} минут.',
                'danger',
            )
            log_audit('login_rate_limit', f'IP: {ip}', severity='warning')
            return render_template('login.html')

        username = sanitize(request.form.get('username', ''), 120)
        password = request.form.get('password', '')

        # Generic failure message — do not reveal whether user exists
        fail_msg = 'Неверное имя пользователя или пароль'

        conn = get_db()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? OR email = ?',
            (username, username),
        ).fetchone()

        if user:
            # Account lockout check
            if user['locked_until']:
                try:
                    locked = datetime.fromisoformat(user['locked_until'])
                    if locked > datetime.now():
                        flash(
                            'Аккаунт временно заблокирован. Попробуйте позже.',
                            'danger',
                        )
                        log_audit(
                            'login_locked',
                            f'User: {username}',
                            user_id=user['id'],
                            severity='warning',
                        )
                        conn.close()
                        return render_template('login.html')
                except (ValueError, TypeError):
                    pass

            if not user['is_active']:
                flash(
                    'Аккаунт деактивирован. Обратитесь к администратору.',
                    'danger',
                )
                log_audit(
                    'login_inactive',
                    f'User: {username}',
                    user_id=user['id'],
                    severity='warning',
                )
                conn.close()
                return render_template('login.html')

            if check_password_hash(user['password_hash'], password):
                # Success: reset counters
                conn.execute(
                    'UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = ?',
                    (user['id'],),
                )
                conn.commit()
                conn.close()

                # Session fixation protection
                session.clear()
                rotate_csrf_token()

                user_obj = User(
                    user['id'],
                    user['username'],
                    user['email'],
                    user['is_admin'],
                    user['is_active'],
                )
                login_user(user_obj, remember=True)
                session.permanent = True
                log_audit(
                    'login_success',
                    f'User: {user["username"]}',
                    user_id=user['id'],
                )
                flash(f'Добро пожаловать, {user["username"]}!', 'success')

                next_page = request.args.get('next')
                if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                    return redirect(next_page)
                return redirect(url_for('main.index'))

            # Wrong password — increment failures / lock
            fails = (user['failed_logins'] or 0) + 1
            locked_until = None
            if fails >= Config.MAX_LOGIN_ATTEMPTS:
                locked_until = (
                    datetime.now() + timedelta(minutes=Config.LOCKOUT_MINUTES)
                ).isoformat()
                fails = 0
            conn.execute(
                'UPDATE users SET failed_logins = ?, locked_until = ? WHERE id = ?',
                (fails, locked_until, user['id']),
            )
            conn.commit()
            record_attempt(_login_attempts, ip)
            log_audit(
                'login_fail',
                f'User: {username}, fails={fails}',
                user_id=user['id'],
                severity='warning',
            )
            flash(fail_msg, 'danger')
        else:
            # Unknown user — still burn a rate-limit slot (anti-enumeration timing)
            record_attempt(_login_attempts, ip)
            log_audit('login_fail', f'Unknown user: {username}', severity='warning')
            # Dummy hash check to reduce timing difference
            check_password_hash(
                'scrypt:32768:8:1$dummy$0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
                password or 'x',
            )
            flash(fail_msg, 'danger')

        conn.close()

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    log_audit('logout', f'User: {current_user.username}')
    logout_user()
    session.clear()
    flash('Вы вышли из аккаунта', 'info')
    return redirect(url_for('main.index'))
