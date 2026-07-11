import hashlib
import logging
import sqlite3
from contextlib import contextmanager
from typing import Any, Generator, Optional

import bcrypt

from .config import get_settings

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("$2"):
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    return hashlib.sha256(password.encode("utf-8")).hexdigest() == password_hash


class Database:
    """SQLite/PostgreSQL-ready database access layer."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._postgres = None
        if self._settings.use_postgres:
            self._init_postgres()

    def _init_postgres(self) -> None:
        try:
            import psycopg2
            import psycopg2.extras

            self._postgres = psycopg2
            self._extras = psycopg2.extras
            logger.info("PostgreSQL mode enabled")
        except ImportError as exc:
            raise RuntimeError(
                "DATABASE_URL is set to PostgreSQL but psycopg2 is not installed. "
                "Install psycopg2-binary or unset DATABASE_URL."
            ) from exc

    @property
    def backend(self) -> str:
        return "postgresql" if self._settings.use_postgres else "sqlite"

    @contextmanager
    def connection(self) -> Generator[Any, None, None]:
        if self._settings.use_postgres:
            conn = self._postgres.connect(self._settings.database_url)
            conn.autocommit = False
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        else:
            self._settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._settings.sqlite_path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def execute(self, sql: str, params: tuple | list = ()) -> Any:
        adapted_sql = self._adapt_sql(sql)
        with self.connection() as conn:
            if self._settings.use_postgres:
                cursor = conn.cursor()
                cursor.execute(adapted_sql, params)
            else:
                cursor = conn.execute(adapted_sql, params)
            return cursor

    def insert(self, sql: str, params: tuple | list = ()) -> int:
        adapted_sql = self._adapt_sql(sql)
        with self.connection() as conn:
            if self._settings.use_postgres:
                if "RETURNING" not in adapted_sql.upper():
                    adapted_sql = adapted_sql.rstrip().rstrip(";") + " RETURNING id"
                cursor = conn.cursor()
                cursor.execute(adapted_sql, params)
                row = cursor.fetchone()
                return int(row[0])
            cursor = conn.execute(adapted_sql, params)
            return int(cursor.lastrowid)

    def fetchone(self, sql: str, params: tuple | list = ()) -> Optional[dict[str, Any]]:
        adapted_sql = self._adapt_sql(sql)
        with self.connection() as conn:
            if self._settings.use_postgres:
                cursor = conn.cursor(cursor_factory=self._extras.RealDictCursor)
                cursor.execute(adapted_sql, params)
                row = cursor.fetchone()
                return dict(row) if row else None
            cursor = conn.execute(adapted_sql, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def fetchall(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        adapted_sql = self._adapt_sql(sql)
        with self.connection() as conn:
            if self._settings.use_postgres:
                cursor = conn.cursor(cursor_factory=self._extras.RealDictCursor)
                cursor.execute(adapted_sql, params)
                return [dict(row) for row in cursor.fetchall()]
            cursor = conn.execute(adapted_sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def _adapt_sql(self, sql: str) -> str:
        if self._settings.use_postgres:
            return sql.replace("?", "%s")
        return sql

    def _column_exists_sqlite(self, conn: sqlite3.Connection, table: str, column: str) -> bool:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(row[1] == column for row in rows)

    def init_db(self) -> None:
        if self._settings.use_postgres:
            self._init_postgres_schema()
        else:
            self._init_sqlite_schema()

    def _init_sqlite_schema(self) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'analyst',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    user_agent TEXT,
                    ip_address TEXT,
                    revoked INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    revoked_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # SQLite only allows constant defaults in ALTER TABLE ADD COLUMN.
            migrations = [
                ("users", "is_active", "INTEGER NOT NULL DEFAULT 1"),
                ("users", "created_at", "TEXT"),
                ("users", "updated_at", "TEXT"),
                ("sessions", "user_agent", "TEXT"),
                ("sessions", "ip_address", "TEXT"),
                ("sessions", "revoked", "INTEGER NOT NULL DEFAULT 0"),
                ("sessions", "revoked_at", "TEXT"),
            ]
            for table, column, definition in migrations:
                if not self._column_exists_sqlite(conn, table, column):
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

            conn.execute(
                "UPDATE users SET created_at = COALESCE(created_at, datetime('now')) WHERE created_at IS NULL"
            )
            conn.execute(
                "UPDATE users SET updated_at = COALESCE(updated_at, datetime('now')) WHERE updated_at IS NULL"
            )

    def _init_postgres_schema(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'analyst',
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                token TEXT UNIQUE NOT NULL,
                user_agent TEXT,
                ip_address TEXT,
                revoked BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                revoked_at TIMESTAMPTZ
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chats (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                title TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                chat_id INTEGER NOT NULL REFERENCES chats(id),
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
        ]
        with self.connection() as conn:
            cursor = conn.cursor()
            for statement in statements:
                cursor.execute(statement)


_db: Optional[Database] = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


def get_connection():
    """Backward-compatible SQLite connection for legacy callers."""
    settings = get_settings()
    if settings.use_postgres:
        raise RuntimeError("Use get_db() for PostgreSQL connections")
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    get_db().init_db()


def seed_demo_user() -> None:
    demo = get_db().fetchone("SELECT id FROM users WHERE email = ?", ("demo@support.ai",))
    if not demo:
        get_db().execute(
            "INSERT INTO users (email, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
            ("demo@support.ai", hash_password("demo123"), "Demo User", "manager"),
        )

    admin = get_db().fetchone("SELECT id FROM users WHERE email = ?", ("admin@support.ai",))
    if not admin:
        get_db().execute(
            "INSERT INTO users (email, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
            ("admin@support.ai", hash_password("admin123"), "Admin User", "admin"),
        )
