import secrets
from typing import Optional

from .database import get_connection, hash_password


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


def create_token() -> str:
    return secrets.token_urlsafe(24)


def authenticate_user(email: str, password: str) -> Optional[dict]:
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if user and verify_password(password, user["password_hash"]):
        return dict(user)
    return None


def create_session(user_id: int) -> str:
    token = create_token()
    conn = get_connection()
    conn.execute("INSERT INTO sessions (user_id, token) VALUES (?, ?)", (user_id, token))
    conn.commit()
    conn.close()
    return token


def validate_session(token: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    conn.close()
    if row:
        conn = get_connection()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (row["user_id"],)).fetchone()
        conn.close()
        return dict(user)
    return None
