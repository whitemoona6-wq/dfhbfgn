"""Tests for catalog, product pages, search, filters."""


class TestIndex:
    def test_index_loads(self, client):
        r = client.get('/')
        assert r.status_code == 200
        assert b'GameGear' in r.data or 'Популярные'.encode() in r.data

    def test_index_has_products(self, client):
        r = client.get('/')
        assert 'В корзину'.encode() in r.data or 'Войти'.encode() in r.data


class TestCatalog:
    def test_catalog_loads(self, client):
        r = client.get('/catalog')
        assert r.status_code == 200
        assert 'Каталог'.encode() in r.data or 'товаров'.encode() in r.data or 'Товары'.encode() in r.data

    def test_catalog_category_filter(self, client):
        r = client.get('/catalog?category=mice')
        assert r.status_code == 200

    def test_catalog_search(self, client):
        r = client.get('/catalog?q=Razer')
        assert r.status_code == 200
        data = r.data.decode()
        assert 'Razer' in data or 'результатов'.lower() in data.lower() or 'ничего' in data.lower()

    def test_catalog_sort_price(self, client):
        r = client.get('/catalog?sort=price_asc')
        assert r.status_code == 200

    def test_catalog_brand_filter(self, client):
        r = client.get('/catalog?brand=Logitech')
        assert r.status_code == 200


class TestProduct:
    def test_product_detail(self, client):
        r = client.get('/product/1')
        assert r.status_code == 200
        assert '₽'.encode() in r.data

    def test_product_not_found(self, client):
        r = client.get('/product/99999', follow_redirects=True)
        assert r.status_code == 200
        assert 'не найден'.encode() in r.data

    def test_product_has_reviews_section(self, client):
        r = client.get('/product/1')
        assert 'Отзыв'.encode() in r.data or 'отзыв'.encode() in r.data
