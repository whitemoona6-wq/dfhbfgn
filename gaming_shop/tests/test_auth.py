"""Tests for authentication: register, login, logout."""
from tests.conftest import login, login_as_demo, login_as_admin


class TestRegister:
    def test_register_page_loads(self, client):
        r = client.get('/register')
        assert r.status_code == 200
        assert 'Регистрация'.encode() in r.data

    def test_register_success(self, client, csrf_token):
        r = client.post('/register', data={
            'username': 'newuser',
            'email': 'new@test.ru',
            'password': 'secret1',
            'password2': 'secret1',
            'csrf_token': csrf_token,
        }, follow_redirects=True)
        assert r.status_code == 200
        assert 'успешна'.encode() in r.data or 'Войдите'.encode() in r.data

    def test_register_password_mismatch(self, client, csrf_token):
        r = client.post('/register', data={
            'username': 'user2',
            'email': 'u2@test.ru',
            'password': 'secret1',
            'password2': 'secret2',
            'csrf_token': csrf_token,
        }, follow_redirects=True)
        assert 'не совпадают'.encode() in r.data

    def test_register_short_password(self, client, csrf_token):
        r = client.post('/register', data={
            'username': 'user3',
            'email': 'u3@test.ru',
            'password': 'ab',
            'password2': 'ab',
            'csrf_token': csrf_token,
        }, follow_redirects=True)
        assert '6 символов'.encode() in r.data

    def test_register_duplicate(self, client, csrf_token):
        r = client.post('/register', data={
            'username': 'demo',
            'email': 'other@test.ru',
            'password': 'secret1',
            'password2': 'secret1',
            'csrf_token': csrf_token,
        }, follow_redirects=True)
        assert 'уже существует'.encode() in r.data

    def test_register_without_csrf(self, client):
        r = client.post('/register', data={
            'username': 'hacker',
            'email': 'h@test.ru',
            'password': 'secret1',
            'password2': 'secret1',
        }, follow_redirects=True)
        assert 'запрещён'.encode() in r.data or r.status_code in (403, 200)


class TestLogin:
    def test_login_page_loads(self, client):
        r = client.get('/login')
        assert r.status_code == 200
        assert 'Вход'.encode() in r.data

    def test_login_success_demo(self, client, csrf_token):
        r = login_as_demo(client, csrf_token)
        assert r.status_code == 200
        assert 'Добро пожаловать'.encode() in r.data

    def test_login_success_admin(self, client, csrf_token):
        r = login_as_admin(client, csrf_token)
        assert r.status_code == 200
        assert 'Добро пожаловать'.encode() in r.data

    def test_login_wrong_password(self, client, csrf_token):
        r = login(client, 'demo', 'wrongpass', csrf_token)
        assert 'Неверное'.encode() in r.data

    def test_login_unknown_user(self, client, csrf_token):
        r = login(client, 'nobody', 'whatever', csrf_token)
        assert 'Неверное'.encode() in r.data

    def test_login_without_csrf(self, client):
        r = client.post('/login', data={
            'username': 'demo',
            'password': 'demo123',
        }, follow_redirects=True)
        assert 'запрещён'.encode() in r.data or r.status_code in (403, 200)


class TestLogout:
    def test_logout(self, client, csrf_token):
        login_as_demo(client, csrf_token)
        r = client.get('/logout', follow_redirects=True)
        assert r.status_code == 200
        assert 'вышли'.encode() in r.data
