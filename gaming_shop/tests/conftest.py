import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from config import TestingConfig
from database import init_db
import config as cfg_mod


@pytest.fixture
def app():
    """Application with isolated temporary database and relaxed password policy."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')

    # Point both Config classes at the temp DB and relax password rules for tests
    for cls in (cfg_mod.Config, cfg_mod.TestingConfig):
        cls.DATABASE = db_path
        cls.PASSWORD_MIN_LENGTH = 6
        cls.PASSWORD_REQUIRE_LETTER = False
        cls.PASSWORD_REQUIRE_DIGIT = False

    TestingConfig.DATABASE = db_path
    application = create_app(TestingConfig)

    with application.app_context():
        init_db()

    yield application

    os.close(db_fd)
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def csrf_token(client):
    """Fresh CSRF token from the login page."""
    import re
    r = client.get('/login')
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.data.decode())
    assert m, 'CSRF token not found on login page'
    return m.group(1)


def _extract_csrf(client):
    import re
    # Any page with a form works after login
    r = client.get('/')
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.data.decode())
    if m:
        return m.group(1)
    r = client.get('/login')
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.data.decode())
    assert m, 'CSRF token not found'
    return m.group(1)


def login(client, username, password, csrf):
    r = client.post('/login', data={
        'username': username,
        'password': password,
        'csrf_token': csrf,
    }, follow_redirects=True)
    return r


def login_as_admin(client, csrf):
    return login(client, 'admin', 'admin123', csrf)


def login_as_demo(client, csrf):
    return login(client, 'demo', 'demo123', csrf)


def fresh_csrf(client):
    """Get CSRF after login (session was rotated)."""
    return _extract_csrf(client)
