"""Security utilities: CSRF, rate limiting, sanitization, audit log, headers.

Design notes
------------
* CSRF tokens are 256-bit random values stored in the server-side session and
  compared with ``hmac.compare_digest`` (constant-time).
* Login / register rate limits are IP-based sliding windows held in memory.
  Account-level lockout is persisted in the ``users`` table.
* All user-controlled strings pass through ``sanitize`` before storage or
  reflection; SQL is always parameterized.
* Audit events are best-effort: failures never break the request path.
"""
from __future__ import annotations

import hmac
import re
import secrets
import time
from collections import defaultdict
from functools import wraps
from typing import Optional

from flask import abort, flash, redirect, request, session, url_for
from flask_login import current_user

from config import Config
from database import get_db

# ---------------------------------------------------------------------------
# In-memory rate-limit stores  (process-local; fine for single-worker demos)
# ---------------------------------------------------------------------------
_login_attempts: dict[str, list[float]] = defaultdict(list)
_register_attempts: dict[str, list[float]] = defaultdict(list)
_global_attempts: dict[str, list[float]] = defaultdict(list)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_client_ip() -> str:
    """Best-effort client IP (respect first X-Forwarded-For hop if present)."""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        # take leftmost (original client); strip port if any
        return forwarded.split(',')[0].strip().split(':')[0] or '0.0.0.0'
    return (request.remote_addr or '0.0.0.0').split(':')[0]


def sanitize(text, max_len: int = 500) -> str:
    """Strip control characters and truncate."""
    if not text:
        return ''
    text = str(text).strip()
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text[:max_len]


def is_valid_email(email: str) -> bool:
    if not email or len(email) > 254:
        return False
    return bool(re.match(
        r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email,
    ))


def is_strong_password(password: str) -> tuple[bool, str]:
    """Enforce configured password policy. Returns (ok, error_message)."""
    min_len = getattr(Config, 'PASSWORD_MIN_LENGTH', 8)
    if len(password) < min_len:
        return False, f'Пароль должен быть не менее {min_len} символов'
    if getattr(Config, 'PASSWORD_REQUIRE_LETTER', True):
        if not re.search(r'[A-Za-zА-Яа-я]', password):
            return False, 'Пароль должен содержать хотя бы одну букву'
    if getattr(Config, 'PASSWORD_REQUIRE_DIGIT', True):
        if not re.search(r'\d', password):
            return False, 'Пароль должен содержать хотя бы одну цифру'
    # Reject extremely common passwords
    common = {
        'password', 'password1', '12345678', 'qwerty123', 'admin123',
        'letmein1', 'welcome1', 'monkey12',
    }
    if password.lower() in common:
        return False, 'Этот пароль слишком распространён, выберите другой'
    return True, ''


def check_rate_limit(store: dict, key: str, max_attempts: int, window_minutes: int) -> bool:
    """Return True if the key is still within the allowed attempt budget."""
    now = time.time()
    window = window_minutes * 60
    store[key] = [t for t in store[key] if now - t < window]
    return len(store[key]) < max_attempts


def record_attempt(store: dict, key: str) -> None:
    store[key].append(time.time())


def log_audit(
    action: str,
    details: str = '',
    user_id: Optional[int] = None,
    severity: str = 'info',
) -> None:
    """Persist a security/audit event. Never raises."""
    try:
        conn = get_db()
        uid = user_id
        if uid is None and getattr(current_user, 'is_authenticated', False):
            uid = current_user.id
        conn.execute(
            '''INSERT INTO audit_log
               (user_id, action, details, ip_address, user_agent, severity)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (
                uid,
                sanitize(action, 80),
                sanitize(details, 1000),
                get_client_ip(),
                sanitize(request.headers.get('User-Agent', ''), 300),
                sanitize(severity, 20),
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------

def generate_csrf_token() -> str:
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def rotate_csrf_token() -> str:
    """Issue a fresh CSRF token (call after privilege changes / login)."""
    session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def validate_csrf() -> None:
    """Abort with 403 if the submitted token does not match the session token."""
    token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token') or ''
    expected = session.get('_csrf_token') or ''
    # Constant-time comparison prevents timing leaks
    if not expected or not hmac.compare_digest(str(token), str(expected)):
        log_audit('csrf_fail', f'Path: {request.path}', severity='warning')
        abort(403)


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            log_audit('admin_access_denied', f'Path: {request.path}', severity='warning')
            flash('Доступ только для администратора', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Response headers
# ---------------------------------------------------------------------------

def set_security_headers(response):
    """Attach defensive HTTP headers to every response."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = (
        'camera=(), microphone=(), geolocation=(), payment=()'
    )
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https: http:; "
        "font-src 'self' https://cdn.jsdelivr.net; "
        "connect-src 'self'; "
        "frame-ancestors 'self'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    # Cross-Origin policies (modern browsers)
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    response.headers['Cross-Origin-Resource-Policy'] = 'same-site'

    if getattr(Config, 'ENABLE_HSTS', False):
        max_age = getattr(Config, 'HSTS_MAX_AGE', 31536000)
        response.headers['Strict-Transport-Security'] = (
            f'max-age={max_age}; includeSubDomains'
        )
    return response
