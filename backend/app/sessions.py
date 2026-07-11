import json
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from .config import get_settings
from .database import get_db
from .redis_client import get_redis


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_token() -> str:
    return secrets.token_urlsafe(32)


class SessionService:
    """Redis-backed session management with database audit trail."""

    def __init__(self) -> None:
        self._redis = get_redis()
        self._settings = get_settings()
        self._db = get_db()

    def _session_key(self, token: str) -> str:
        return f"session:{token}"

    def _user_sessions_key(self, user_id: int) -> str:
        return f"user:{user_id}:sessions"

    def create_session(
        self,
        user_id: int,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        token = create_token()
        ttl = self._settings.session_ttl_seconds
        payload = {
            "user_id": user_id,
            "token": token,
            "created_at": _utcnow_iso(),
            "user_agent": user_agent,
            "ip_address": ip_address,
        }
        self._redis.set(self._session_key(token), json.dumps(payload), ex=ttl)
        self._redis.sadd(self._user_sessions_key(user_id), token)
        self._redis.expire(self._user_sessions_key(user_id), self._settings.session_refresh_ttl_seconds)

        self._db.execute(
            "INSERT INTO sessions (user_id, token, user_agent, ip_address) VALUES (?, ?, ?, ?)",
            (user_id, token, user_agent, ip_address),
        )
        return token

    def validate_session(self, token: str) -> Optional[dict[str, Any]]:
        raw = self._redis.get(self._session_key(token))
        if raw:
            data = json.loads(raw)
            user = self._get_user(data["user_id"])
            if user and user.get("is_active", 1):
                return user
            return None

        row = self._db.fetchone("SELECT * FROM sessions WHERE token = ? AND revoked = 0", (token,))
        if not row:
            return None
        user = self._db.fetchone("SELECT * FROM users WHERE id = ? AND is_active = 1", (row["user_id"],))
        if not user:
            return None

        self._redis.set(
            self._session_key(token),
            json.dumps(
                {
                    "user_id": row["user_id"],
                    "token": token,
                    "created_at": str(row["created_at"]),
                    "user_agent": row["user_agent"],
                    "ip_address": row["ip_address"],
                }
            ),
            ex=self._settings.session_ttl_seconds,
        )
        self._redis.sadd(self._user_sessions_key(row["user_id"]), token)
        return user

    def refresh_session(self, token: str) -> bool:
        if not self._redis.exists(self._session_key(token)):
            return False
        return self._redis.expire(self._session_key(token), self._settings.session_ttl_seconds)

    def revoke_session(self, token: str, user_id: Optional[int] = None) -> bool:
        self._redis.delete(self._session_key(token))
        if user_id is not None:
            self._redis.srem(self._user_sessions_key(user_id), token)

        row = self._db.fetchone("SELECT user_id FROM sessions WHERE token = ?", (token,))
        if not row:
            return False
        self._db.execute(
            "UPDATE sessions SET revoked = 1, revoked_at = CURRENT_TIMESTAMP WHERE token = ?",
            (token,),
        )
        self._redis.srem(self._user_sessions_key(row["user_id"]), token)
        return True

    def revoke_all_sessions(self, user_id: int, except_token: Optional[str] = None) -> int:
        tokens = self._redis.smembers(self._user_sessions_key(user_id))
        revoked = 0
        for token in tokens:
            if except_token and token == except_token:
                continue
            if self.revoke_session(token, user_id=user_id):
                revoked += 1
        return revoked

    def list_sessions(self, user_id: int) -> list[dict[str, Any]]:
        tokens = self._redis.smembers(self._user_sessions_key(user_id))
        sessions: list[dict[str, Any]] = []

        for token in tokens:
            raw = self._redis.get(self._session_key(token))
            if raw:
                data = json.loads(raw)
                row = self._db.fetchone(
                    "SELECT id, created_at, user_agent, ip_address FROM sessions WHERE token = ? AND revoked = 0",
                    (token,),
                )
                sessions.append(
                    {
                        "id": row["id"] if row else None,
                        "token_preview": f"{token[:8]}...",
                        "token": token,
                        "created_at": data.get("created_at") or (str(row["created_at"]) if row else None),
                        "user_agent": data.get("user_agent") or (row["user_agent"] if row else None),
                        "ip_address": data.get("ip_address") or (row["ip_address"] if row else None),
                    }
                )
            else:
                row = self._db.fetchone(
                    "SELECT id, token, created_at, user_agent, ip_address FROM sessions WHERE token = ? AND revoked = 0",
                    (token,),
                )
                if row:
                    sessions.append(
                        {
                            "id": row["id"],
                            "token_preview": f"{row['token'][:8]}...",
                            "token": row["token"],
                            "created_at": str(row["created_at"]),
                            "user_agent": row["user_agent"],
                            "ip_address": row["ip_address"],
                        }
                    )
        return sessions

    def _get_user(self, user_id: int) -> Optional[dict[str, Any]]:
        return self._db.fetchone("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,))


_session_service: Optional[SessionService] = None


def get_session_service() -> SessionService:
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service
