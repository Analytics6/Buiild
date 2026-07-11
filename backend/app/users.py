import re
from typing import Any, Optional

from .config import get_settings
from .database import get_db, hash_password, verify_password

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserService:
    """User CRUD with role-based access."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._db = get_db()

    def _validate_role(self, role: str) -> str:
        if role not in self._settings.valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(self._settings.valid_roles)}")
        return role

    def _public_user(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "email": row["email"],
            "full_name": row["full_name"],
            "role": row["role"],
            "is_active": bool(row.get("is_active", 1)),
            "created_at": str(row.get("created_at")) if row.get("created_at") else None,
            "updated_at": str(row.get("updated_at")) if row.get("updated_at") else None,
        }

    def register(
        self,
        email: str,
        password: str,
        full_name: str,
        role: str = "analyst",
    ) -> dict[str, Any]:
        email = email.strip().lower()
        if not EMAIL_PATTERN.match(email):
            raise ValueError("Invalid email address")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters")
        if not full_name.strip():
            raise ValueError("Full name is required")
        role = self._validate_role(role)

        existing = self._db.fetchone("SELECT id FROM users WHERE email = ?", (email,))
        if existing:
            raise ValueError("Email already registered")

        user_id = self._db.insert(
            "INSERT INTO users (email, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
            (email, hash_password(password), full_name.strip(), role),
        )
        user = self._db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
        return self._public_user(user)

    def authenticate(self, email: str, password: str) -> Optional[dict[str, Any]]:
        user = self._db.fetchone(
            "SELECT * FROM users WHERE email = ? AND is_active = 1",
            (email.strip().lower(),),
        )
        if user and verify_password(password, user["password_hash"]):
            return user
        return None

    def get_by_id(self, user_id: int) -> Optional[dict[str, Any]]:
        user = self._db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
        return self._public_user(user) if user else None

    def list_users(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        if include_inactive:
            rows = self._db.fetchall("SELECT * FROM users ORDER BY id ASC")
        else:
            rows = self._db.fetchall("SELECT * FROM users WHERE is_active = 1 ORDER BY id ASC")
        return [self._public_user(row) for row in rows]

    def update_user(
        self,
        user_id: int,
        *,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        role: Optional[str] = None,
        password: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[dict[str, Any]]:
        user = self._db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
        if not user:
            return None

        updates: list[str] = []
        params: list[Any] = []

        if email is not None:
            email = email.strip().lower()
            if not EMAIL_PATTERN.match(email):
                raise ValueError("Invalid email address")
            existing = self._db.fetchone("SELECT id FROM users WHERE email = ? AND id != ?", (email, user_id))
            if existing:
                raise ValueError("Email already in use")
            updates.append("email = ?")
            params.append(email)

        if full_name is not None:
            if not full_name.strip():
                raise ValueError("Full name is required")
            updates.append("full_name = ?")
            params.append(full_name.strip())

        if role is not None:
            updates.append("role = ?")
            params.append(self._validate_role(role))

        if password is not None:
            if len(password) < 6:
                raise ValueError("Password must be at least 6 characters")
            updates.append("password_hash = ?")
            params.append(hash_password(password))

        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)

        if not updates:
            return self._public_user(user)

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(user_id)
        self._db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        updated = self._db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
        return self._public_user(updated)

    def delete_user(self, user_id: int, *, hard: bool = False) -> bool:
        user = self._db.fetchone("SELECT id FROM users WHERE id = ?", (user_id,))
        if not user:
            return False
        if hard:
            self._db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        else:
            self._db.execute(
                "UPDATE users SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (user_id,),
            )
        return True


_user_service: Optional[UserService] = None


def get_user_service() -> UserService:
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service
