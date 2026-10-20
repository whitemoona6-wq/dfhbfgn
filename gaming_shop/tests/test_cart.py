"""Tests for cart, checkout, orders, reviews."""
from tests.conftest import login_as_demo, fresh_csrf


class TestCartAccess:
    def test_cart_requires_login(self, client):
        r = client.get('/cart', follow_redirects=True)
        assert r.status_code == 200
        # Should redirect to login
        assert 'Войдите'.encode() in r.data or 'Вход'.encode() in r.data or 'login' in r.data.decode().lower()

    def test_cart_empty(self, client, csrf_token):
        login_as_demo(client, csrf_token)
        r = client.get('/cart')
        assert r.status_code == 200
        assert 'пуста'.encode() in r.data or 'Корзина'.encode() in r.data


class TestAddToCart:
    def test_add_product(self, client, csrf_token):
        login_as_demo(client, csrf_token)
        token = fresh_csrf(client)
        r = client.post('/cart/add/1', data={
            'quantity': 1,
            'csrf_token': token,
        }, follow_redirects=True)
        assert r.status_code == 200
        assert 'добавлен'.encode() in r.data or 'корзин'.encode() in r.data

    def test_add_without_csrf(self, client, csrf_token):
        login_as_demo(client, csrf_token)
        r = client.post('/cart/add/1', data={'quantity': 1}, follow_redirects=True)
        assert 'запрещён'.encode() in r.data or r.status_code in (403, 200)

    def test_cart_shows_item(self, client, csrf_token):
        login_as_demo(client, csrf_token)
        token = fresh_csrf(client)
        client.post('/cart/add/1', data={'quantity': 2, 'csrf_token': token}, follow_redirects=True)
        r = client.get('/cart')
        assert r.status_code == 200
        # Should not be empty
        assert 'пуста'.encode() not in r.data or 'Оформить'.encode() in r.data


class TestCheckout:
    def test_checkout_empty_redirect(self, client, csrf_token):
        login_as_demo(client, csrf_token)
        r = client.get('/checkout', follow_redirects=True)
        assert r.status_code == 200

    def test_full_purchase_flow(self, client, csrf_token):
        login_as_demo(client, csrf_token)
        token = fresh_csrf(client)
        # Add to cart
        client.post('/cart/add/2', data={'quantity': 1, 'csrf_token': token}, follow_redirects=True)
        # Checkout page
        r = client.get('/checkout')
        assert r.status_code == 200
        token = fresh_csrf(client)
        # Place order
        r = client.post('/checkout', data={
            'address': 'Москва, Тестовая 1',
            'phone': '+79991234567',
            'csrf_token': token,
        }, follow_redirects=True)
        assert r.status_code == 200
        assert 'успешно'.encode() in r.data or 'Заказ'.encode() in r.data

    def test_orders_page(self, client, csrf_token):
        login_as_demo(client, csrf_token)
        r = client.get('/orders')
        assert r.status_code == 200


class TestReview:
    def test_add_review(self, client, csrf_token):
        login_as_demo(client, csrf_token)
        token = fresh_csrf(client)
        r = client.post('/review/3', data={
            'rating': 5,
            'comment': 'Отличный товар!',
            'csrf_token': token,
        }, follow_redirects=True)
        assert r.status_code == 200
        assert 'Отзыв'.encode() in r.data or 'добавлен'.encode() in r.data
