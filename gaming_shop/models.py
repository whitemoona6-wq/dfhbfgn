from flask_login import UserMixin
from database import get_db
from extensions import login_manager


class User(UserMixin):
    def __init__(self, id, username, email, is_admin=False, is_active=True):
        self.id = id
        self.username = username
        self.email = email
        self.is_admin = is_admin
        self._is_active = is_active

    @property
    def is_active(self):
        return bool(self._is_active)


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user and user['is_active']:
        return User(
            user['id'], user['username'], user['email'],
            user['is_admin'], user['is_active'],
        )
    return None
