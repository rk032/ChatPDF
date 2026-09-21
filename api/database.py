import sqlite3
import hashlib
import os
from contextlib import contextmanager

from werkzeug.security import generate_password_hash, check_password_hash

from .models import User


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)

        try:
            yield conn
        finally:
            conn.close()

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    user_id TEXT UNIQUE NOT NULL
                )
                """
            )

            conn.commit()

    def create_user(self, email: str, password: str) -> User:

        user_id = hashlib.md5(
            email.lower().encode()
        ).hexdigest()

        password_hash = generate_password_hash(password)

        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO users
                (email, password, user_id)
                VALUES (?, ?, ?)
                """,
                (
                    email,
                    password_hash,
                    user_id,
                ),
            )

            conn.commit()

        return User(
            email=email,
            user_id=user_id,
            password=password_hash,
        )

    def get_user_by_email(self, email: str):

        with self.get_connection() as conn:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT email, password, user_id
                FROM users
                WHERE email = ?
                """,
                (email,),
            )

            row = cursor.fetchone()

            if row:
                return User(
                    email=row[0],
                    password=row[1],
                    user_id=row[2],
                )

        return None

    def verify_password(
        self,
        password: str,
        password_hash: str,
    ) -> bool:

        return check_password_hash(
            password_hash,
            password,
        )


def get_db():

    db = Database(
        os.getenv(
            "DB_PATH",
            "chat_app.db",
        )
    )

    return db