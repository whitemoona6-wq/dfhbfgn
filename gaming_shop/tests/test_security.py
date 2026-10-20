"""Tests for security features: headers, CSRF, sanitize, audit."""
from security import sanitize, is_valid_email, is_strong_password


class TestSecurityHeaders:
    def test_x_frame_options(self, client):
        r = client.get('/')
        assert r.headers.get('X-Frame-Options') == 'SAMEORIGIN'

    def test_x_content_type(self, client):
        r = client.get('/')
        assert r.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_csp_present(self, client):
        r = client.get('/')
        assert 'Content-Security-Policy' in r.headers

    def test_xss_protection(self, client):
        r = client.get('/')
        assert r.headers.get('X-XSS-Protection') == '1; mode=block'

    def test_referrer_policy(self, client):
        r = client.get('/')
        assert r.headers.get('Referrer-Policy') is not None

    def test_coop(self, client):
        r = client.get('/')
        assert r.headers.get('Cross-Origin-Opener-Policy') == 'same-origin'


class TestCSRF:
    def test_csrf_token_in_login(self, client):
        r = client.get('/login')
        assert b'csrf_token' in r.data

    def test_csrf_token_in_register(self, client):
        r = client.get('/register')
        assert b'csrf_token' in r.data

    def test_post_without_csrf_blocked(self, client):
        r = client.post('/login', data={
            'username': 'admin',
            'password': 'admin123',
        }, follow_redirects=True)
        # Should be blocked or redirected with error
        assert 'запрещён'.encode() in r.data or 'Добро пожаловать'.encode() not in r.data


class TestSanitize:
    def test_sanitize_strips(self):
        assert sanitize('  hello  ') == 'hello'

    def test_sanitize_max_len(self):
        assert len(sanitize('a' * 1000, max_len=10)) == 10

    def test_sanitize_control_chars(self):
        assert '\x00' not in sanitize('test\x00data')

    def test_sanitize_none(self):
        assert sanitize(None) == ''


class TestValidation:
    def test_valid_email(self):
        assert is_valid_email('user@example.com')
        assert is_valid_email('a.b@c.co')

    def test_invalid_email(self):
        assert not is_valid_email('not-an-email')
        assert not is_valid_email('@nodomain.com')
        assert not is_valid_email('')

    def test_strong_password(self):
        # Under TestingConfig policy is relaxed (min 6, no letter/digit req)
        ok, msg = is_strong_password('abcdef')
        assert ok, msg

    def test_weak_password(self):
        ok, msg = is_strong_password('ab')
        assert not ok
        assert 'символ' in msg


class TestAuditLog:
    def test_login_creates_audit(self, client, csrf_token):
        from tests.conftest import login_as_demo
        from database import get_db

        login_as_demo(client, csrf_token)
        conn = get_db()
        count = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action='login_success'"
        ).fetchone()[0]
        conn.close()
        assert count >= 1
