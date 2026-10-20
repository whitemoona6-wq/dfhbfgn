import sqlite3
import os
from werkzeug.security import generate_password_hash
from config import Config


def get_db():
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    """Create tables and seed data if empty."""
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        failed_logins INTEGER DEFAULT 0,
        locked_until TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        icon TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        old_price REAL,
        category_id INTEGER,
        image_url TEXT,
        stock INTEGER DEFAULT 50,
        brand TEXT,
        rating REAL DEFAULT 4.5,
        features TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id),
        UNIQUE(user_id, product_id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        total REAL NOT NULL,
        status TEXT DEFAULT 'pending',
        address TEXT,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        rating INTEGER NOT NULL,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        details TEXT,
        ip_address TEXT,
        user_agent TEXT,
        severity TEXT DEFAULT 'info',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    for col, typedef in [
        ('is_active', 'INTEGER DEFAULT 1'),
        ('failed_logins', 'INTEGER DEFAULT 0'),
        ('locked_until', 'TIMESTAMP'),
    ]:
        try:
            c.execute(f'ALTER TABLE users ADD COLUMN {col} {typedef}')
        except sqlite3.OperationalError:
            pass

    conn.commit()

    c.execute('SELECT COUNT(*) FROM categories')
    if c.fetchone()[0] == 0:
        _seed(c)
        conn.commit()

    conn.close()


def _seed(c):
    categories = [
        ('Мыши', 'mice', '🖱️'),
        ('Клавиатуры', 'keyboards', '⌨️'),
        ('Наушники', 'headsets', '🎧'),
        ('Коврики', 'mousepads', '🖼️'),
        ('Геймпады', 'controllers', '🎮'),
        ('Мониторы', 'monitors', '🖥️'),
    ]
    c.executemany('INSERT INTO categories (name, slug, icon) VALUES (?, ?, ?)', categories)

    products = [
        ('Logitech G Pro X Superlight 2', 'Легчайшая беспроводная игровая мышь весом всего 60г. Сенсор HERO 2, 32K DPI.', 14990, 17990, 1, 'https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=400', 25, 'Logitech', 4.9, '60г, 32K DPI, 95 часов батареи, Lightspeed'),
        ('Razer Viper V3 Pro', 'Профессиональная киберспортивная мышь. Focus Pro 30K сенсор, 54г.', 13990, None, 1, 'https://images.unsplash.com/photo-1615662977969-6c2d7c0e2e5c?w=400', 30, 'Razer', 4.8, '54г, 30K DPI, 90 часов, HyperSpeed'),
        ('SteelSeries Aerox 5 Wireless', 'Ультралёгкая мышь с RGB и боковыми кнопками. 74г.', 9990, 12990, 1, 'https://images.unsplash.com/photo-1563297007-0686b7003af7?w=400', 40, 'SteelSeries', 4.6, '74г, 18K DPI, AquaGuard, RGB'),
        ('Zowie EC2-CW', 'Беспроводная версия легендарной EC2. Эргономичная форма.', 11990, None, 1, 'https://images.unsplash.com/photo-1591488320449-011701bb6704?w=400', 15, 'Zowie', 4.7, 'Эргономика, 3200 DPI, беспроводная'),
        ('Razer BlackWidow V4 Pro', 'Механическая клавиатура с OLED дисплеем и Command Dial.', 24990, 29990, 2, 'https://images.unsplash.com/photo-1541140532154-b024d705b90a?w=400', 20, 'Razer', 4.8, 'Razer Green, OLED, Command Dial, RGB'),
        ('Keychron Q1 Pro', 'Кастомная механическая клавиатура 75%. Беспроводная, Gasket Mount.', 18990, None, 2, 'https://images.unsplash.com/photo-1587829741301-dc430b73f898?w=400', 35, 'Keychron', 4.9, 'Gasket Mount, Hot-swap, Bluetooth/2.4G'),
        ('Corsair K70 RGB Pro', 'Алюминиевая рамка, переключатели Cherry MX, медиа-колёсико.', 16990, 19990, 2, 'https://images.unsplash.com/photo-1595225476474-87563907a212?w=400', 28, 'Corsair', 4.7, 'Cherry MX Red, RGB, Aluminum'),
        ('Logitech G915 TKL', 'Низкопрофильная беспроводная механика. Lightspeed + Bluetooth.', 21990, None, 2, 'https://images.unsplash.com/photo-1511467687858-23d96c32e4ae?w=400', 18, 'Logitech', 4.6, 'GL Tactile, TKL, 40 часов'),
        ('HyperX Cloud III', 'Легендарный комфорт. 53мм драйверы, съёмный микрофон.', 8990, 10990, 3, 'https://images.unsplash.com/photo-1618366712010-f4ae9c647dcb?w=400', 50, 'HyperX', 4.8, '53мм, DTS, Memory foam, USB/3.5mm'),
        ('SteelSeries Arctis Nova Pro Wireless', 'Премиум беспроводная гарнитура с активным шумоподавлением.', 34990, None, 3, 'https://images.unsplash.com/photo-1546435770-a3e426bf472b?w=400', 12, 'SteelSeries', 4.9, 'ANC, Dual battery, 360° Spatial'),
        ('Razer BlackShark V2 Pro', 'Киберспортивная гарнитура с THX Spatial Audio.', 15990, 18990, 3, 'https://images.unsplash.com/photo-1484704849700-f032a568e944?w=400', 22, 'Razer', 4.7, 'THX, 50мм, HyperClear mic'),
        ('Sony INZONE H9', 'Беспроводные с ANC и 360 Spatial Sound от Sony.', 27990, None, 3, 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400', 15, 'Sony', 4.5, 'ANC, 360 Spatial, 32 часа'),
        ('SteelSeries QcK Heavy XXL', 'Толстый тканевый коврик 900x400x4мм.', 2990, 3490, 4, 'https://images.unsplash.com/photo-1616587894289-86480e533129?w=400', 100, 'SteelSeries', 4.8, '900x400, 4мм, ткань'),
        ('Artisan Zero Soft XL', 'Премиум японский коврик. Контроль и скорость.', 5990, None, 4, 'https://images.unsplash.com/photo-1625948515291-69613efd103f?w=400', 40, 'Artisan', 4.9, 'Soft, XL, Япония'),
        ('Razer Firefly V2', 'RGB коврик с микротекстурированной поверхностью.', 4990, 5990, 4, 'https://images.unsplash.com/photo-1527814050087-3793815479db?w=400', 60, 'Razer', 4.5, 'RGB, Hard, Chroma'),
        ('Sony DualSense Edge', 'Профессиональный геймпад с сменными стиками и кнопками.', 19990, None, 5, 'https://images.unsplash.com/photo-1606144042614-b2417e99c4e3?w=400', 25, 'Sony', 4.8, 'Сменные модули, Trigger stops, PC/PS5'),
        ('Xbox Elite Series 2', 'Премиум геймпад с настраиваемыми стиками и кнопками.', 17990, 19990, 5, 'https://images.unsplash.com/photo-1621259182978-fbf93132d53d?w=400', 30, 'Microsoft', 4.7, 'Сменные стики, Hair Triggers, 40 часов'),
        ('Razer Wolverine V2 Chroma', 'Проводной геймпад с RGB и дополнительными кнопками.', 9990, None, 5, 'https://images.unsplash.com/photo-1592840496694-26d035b52b48?w=400', 35, 'Razer', 4.6, 'RGB, Mecha-Tactile, PC/Xbox'),
        ('ASUS ROG Swift PG27AQDM', '27" OLED 240Hz, 0.03ms, HDR10.', 89990, 99990, 6, 'https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=400', 8, 'ASUS', 4.9, 'OLED, 240Hz, 0.03ms, G-Sync'),
        ('LG UltraGear 27GP950', '27" 4K 144Hz Nano IPS, HDMI 2.1.', 54990, 64990, 6, 'https://images.unsplash.com/photo-1593640408182-31c70c8268f5?w=400', 12, 'LG', 4.7, '4K, 144Hz, HDMI 2.1, HDR600'),
        ('Samsung Odyssey G7 32"', '32" QHD 240Hz, 1000R, VA.', 39990, 44990, 6, 'https://images.unsplash.com/photo-1616763355548-1b606f371b53?w=400', 15, 'Samsung', 4.6, 'QHD, 240Hz, 1000R, HDR600'),
    ]
    c.executemany(
        '''INSERT INTO products
           (name, description, price, old_price, category_id, image_url, stock, brand, rating, features)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        products,
    )

    c.execute(
        'INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)',
        ('admin', 'admin@gamingshop.ru', generate_password_hash('admin123'), 1),
    )
    c.execute(
        'INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)',
        ('demo', 'demo@mail.ru', generate_password_hash('demo123'), 0),
    )
