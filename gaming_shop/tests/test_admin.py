"""Tests for admin panel functions."""
from tests.conftest import login_as_admin, login_as_demo, fresh_csrf


class TestAdminAccess:
    def test_admin_requires_login(self, client):
        r = client.get('/admin', follow_redirects=True)
        assert r.status_code == 200
        assert 'администратора'.encode() in r.data or 'Войдите'.encode() in r.data or 'Вход'.encode() in r.data

    def test_admin_denied_for_user(self, client, csrf_token):
        login_as_demo(client, csrf_token)
        r = client.get('/admin', follow_redirects=True)
        assert r.status_code == 200
        assert 'администратора'.encode() in r.data

    def test_admin_allowed(self, client, csrf_token):
        login_as_admin(client, csrf_token)
        r = client.get('/admin')
        assert r.status_code == 200
        assert 'Админ'.encode() in r.data


class TestAdminTabs:
    def test_orders_tab(self, client, csrf_token):
        login_as_admin(client, csrf_token)
        r = client.get('/admin?tab=orders')
        assert r.status_code == 200

    def test_products_tab(self, client, csrf_token):
        login_as_admin(client, csrf_token)
        r = client.get('/admin?tab=products')
        assert r.status_code == 200
        assert 'Товар'.encode() in r.data

    def test_users_tab(self, client, csrf_token):
        login_as_admin(client, csrf_token)
        r = client.get('/admin?tab=users')
        assert r.status_code == 200
        assert 'demo'.encode() in r.data or 'Пользовател'.encode() in r.data

    def test_reviews_tab(self, client, csrf_token):
        login_as_admin(client, csrf_token)
        r = client.get('/admin?tab=reviews')
        assert r.status_code == 200

    def test_audit_tab(self, client, csrf_token):
        login_as_admin(client, csrf_token)
        r = client.get('/admin?tab=audit')
        assert r.status_code == 200
        assert 'аудит'.encode() in r.data or 'Аудит'.encode() in r.data or 'login'.encode() in r.data


class TestAdminActions:
    def test_update_product(self, client, csrf_token):
        login_as_admin(client, csrf_token)
        token = fresh_csrf(client)
        r = client.post('/admin/product/1/update', data={
            'price': 13000,
            'stock': 15,
            'csrf_token': token,
        }, follow_redirects=True)
        assert r.status_code == 200
        assert 'обновлён'.encode() in r.data

    def test_toggle_user_active(self, client, csrf_token):
        login_as_admin(client, csrf_token)
        token = fresh_csrf(client)
        # demo user is id=2
        r = client.post('/admin/user/2/toggle_active', data={
            'csrf_token': token,
        }, follow_redirects=True)
        assert r.status_code == 200
        assert 'деактивирован'.encode() in r.data or 'активирован'.encode() in r.data

    def test_cannot_deactivate_self(self, client, csrf_token):
        login_as_admin(client, csrf_token)
        token = fresh_csrf(client)
        r = client.post('/admin/user/1/toggle_active', data={
            'csrf_token': token,
        }, follow_redirects=True)
        assert 'самого себя'.encode() in r.data
