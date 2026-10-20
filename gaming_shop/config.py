"""Application configuration.

Security-sensitive values should be set via environment variables in production:
  SECRET_KEY, SESSION_COOKIE_SECURE=1
"""
import os
import secrets
from datetime import timedelta


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ('1', 'true', 'yes', 'on')


class Config:
    # --- Core ---
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shop.db')

    # --- Session / cookies ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = _env_bool('SESSION_COOKIE_SECURE', False)
    SESSION_COOKIE_NAME = '__Host-session' if _env_bool('SESSION_COOKIE_SECURE') else 'session'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024  # 1 MB request body limit

    # --- Auth rate limits ---
    MAX_LOGIN_ATTEMPTS = 5          # per IP window + per account
    LOCKOUT_MINUTES = 15
    MAX_REGISTER_ATTEMPTS = 3       # per IP / 30 min
    LOGIN_WINDOW_MINUTES = 15

    # --- Password policy ---
    PASSWORD_MIN_LENGTH = 8
    # Require at least one letter and one digit
    PASSWORD_REQUIRE_LETTER = True
    PASSWORD_REQUIRE_DIGIT = True

    # --- Security headers ---
    ENABLE_HSTS = _env_bool('ENABLE_HSTS', False)  # only behind HTTPS
    HSTS_MAX_AGE = 31536000  # 1 year


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True
    ENABLE_HSTS = True
    SESSION_COOKIE_NAME = '__Host-session'


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = 'test-secret-key-not-for-production'
    PASSWORD_MIN_LENGTH = 6  # relaxed for unit tests
    PASSWORD_REQUIRE_LETTER = False
    PASSWORD_REQUIRE_DIGIT = False
