# GameGear — магазин игровой периферии

Полнофункциональное Flask-приложение: каталог, корзина, заказы, отзывы, админ-панель с аудитом и тестами.

## Быстрый старт

```bash
cd gaming_shop
pip install flask flask-login
python3 app.py
# → http://127.0.0.1:5000
```

### Демо-аккаунты

| Роль | Логин | Пароль |
|------|-------|--------|
| Пользователь | `demo` | `demo123` |
| Админ | `admin` | `admin123` |

## Возможности

- Каталог с фильтрами (категория, бренд, поиск, сортировка)
- Корзина, оформление заказа, история заказов
- Отзывы с рейтингом
- Регистрация / вход / выход
- Админ: заказы, товары, пользователи, модерация отзывов, **аудит-лог**
- CSRF, rate-limit, блокировка аккаунта, security headers

Подробнее о защите: **[SECURITY.md](SECURITY.md)**.

## Структура проекта

```
gaming_shop/
├── app.py              # Application factory (create_app)
├── config.py           # Config / ProductionConfig / TestingConfig
├── extensions.py       # Flask-Login
├── database.py         # SQLite schema + seed
├── models.py           # User
├── security.py         # CSRF, rate-limit, sanitize, audit, headers
├── routes/
│   ├── main.py         # /, /catalog, /product/<id>
│   ├── auth.py         # /login, /register, /logout
│   ├── cart.py         # корзина, checkout, заказы, отзывы, профиль
│   └── admin.py        # /admin + управление
├── templates/          # Jinja2
├── static/             # CSS, JS
├── tests/              # pytest (60+ тестов)
├── SECURITY.md
└── shop.db             # создаётся при первом запуске
```

## Тесты

```bash
pip install pytest
python3 -m pytest tests/ -v
```

Покрытие: auth, catalog, cart/checkout, admin, security headers/CSRF/sanitize.

## Конфигурация окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `SECRET_KEY` | Ключ подписи сессий | случайный при старте |
| `SESSION_COOKIE_SECURE` | Cookie только по HTTPS | `0` |
| `ENABLE_HSTS` | Заголовок HSTS | `0` |

Пример production:

```bash
export SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
export SESSION_COOKIE_SECURE=1
export ENABLE_HSTS=1
gunicorn -w 4 -b 0.0.0.0:8000 'app:create_app()'
```

## Лицензия

Демонстрационный учебный проект.
