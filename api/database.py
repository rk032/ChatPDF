# api/database.py
import sqlite3
from contextlib import contextmanager
import hashlib
from models import User
import os

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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    user_id TEXT UNIQUE NOT NULL
                )
            """)
            conn.commit()

    def create_user(self, email: str, password: str) -> User:
        user_id = hashlib.md5(email.lower().encode()).hexdigest()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (email, password, user_id) VALUES (?, ?, ?)",
                (email, password, user_id)  # Store password as plain text
            )
            conn.commit()
        return User(email=email, user_id=user_id, password=password)


    def get_user_by_email(self, email: str) :
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT email, password, user_id FROM users WHERE email = ?",
                (email,)
            )
            user = cursor.fetchone()
            if user:
                return User(
                    email=user[0],
                    password=user[1],
                    user_id=user[2]
                )
        return None

def get_db():
    db = Database(os.getenv("DB_PATH", "chat_app.db"))
    return db