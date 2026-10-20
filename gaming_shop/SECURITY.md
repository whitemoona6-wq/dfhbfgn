# Безопасность GameGear

Документ описывает реализованные меры защиты и рекомендации по развёртыванию.

## Угрозы и меры

| Угроза | Мера |
|--------|------|
| CSRF | Токен 256 bit в сессии, проверка через `hmac.compare_digest`, ротация после логина |
| XSS | Jinja2 autoescape, CSP (`default-src 'self'`), санитизация ввода |
| SQL Injection | Только параметризованные запросы SQLite |
| Session fixation | `session.clear()` перед `login_user`, ротация CSRF |
| Brute-force логина | Лимит попыток по IP + блокировка аккаунта в БД |
| Перечисление пользователей | Единое сообщение об ошибке входа; dummy hash check |
| Clickjacking | `X-Frame-Options: SAMEORIGIN`, CSP `frame-ancestors` |
| MIME sniffing | `X-Content-Type-Options: nosniff` |
| Слабые пароли | Мин. 8 символов, буква + цифра, блокlist распространённых |
| Хранение паролей | `scrypt` (Werkzeug) |
| Утечка через кэш | `Cache-Control: no-store` |
| Admin abuse | Роль `is_admin`, декоратор, аудит всех действий |

## HTTP-заголовки

На каждый ответ добавляются:

- `Content-Security-Policy`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy`
- `Cross-Origin-Opener-Policy: same-origin`
- `Cross-Origin-Resource-Policy: same-site`
- `Cache-Control: no-store`
- `Strict-Transport-Security` — только если `ENABLE_HSTS=1`

## Rate limiting

| Действие | Лимит | Окно |
|----------|-------|------|
| Логин (IP) | 5 | 15 мин |
| Регистрация (IP) | 3 | 30 мин |
| Ошибки пароля (аккаунт) | 5 → lock | 15 мин |

Хранилище лимитов — in-memory (подходит для одного воркера). В продакшене замените на Redis.

## Аудит

Таблица `audit_log` фиксирует:

- `login_success` / `login_fail` / `login_locked` / `login_rate_limit`
- `register` / `register_duplicate` / `register_rate_limit`
- `csrf_fail`, `admin_access_denied`
- `order_created`, `order_status_change`
- `user_activated` / `user_deactivated` / `user_admin_toggle` / `user_unlocked`
- `product_update`, `review_deleted`, `audit_cleared`

Просмотр: **Админ → Аудит-лог**.

## Рекомендации для production

1. Задайте сильный `SECRET_KEY` через окружение (не коммитьте в git).
2. Включите HTTPS и:
   ```bash
   export SESSION_COOKIE_SECURE=1
   export ENABLE_HSTS=1
   ```
3. Запускайте за reverse-proxy (nginx) с ограничением размера тела и TLS.
4. Не используйте `debug=True`.
5. Регулярно проверяйте аудит-лог на аномалии.
6. Делайте бэкапы `shop.db`.
7. При горизонтальном масштабировании вынесите rate-limit и сессии во внешнее хранилище.

## Ответственность

Это учебный/демо-проект. Для реальной коммерции добавьте:

- 2FA для администраторов
- WAF / fail2ban на уровне инфраструктуры
- Централизованный SIEM для audit_log
- Регулярные dependency updates (`pip audit`)
