import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def _reset_singletons() -> None:
    import backend.app.cache as cache_mod
    import backend.app.chroma_store as chroma_mod
    import backend.app.database as db_mod
    import backend.app.rag_chain as rag_mod
    import backend.app.redis_client as redis_mod
    import backend.app.sessions as sessions_mod
    import backend.app.users as users_mod
    from backend.app.config import get_settings

    get_settings.cache_clear()
    redis_mod._redis_client = None
    cache_mod._cache_service = None
    cache_mod._rate_limiter = None
    db_mod._db = None
    users_mod._user_service = None
    sessions_mod._session_service = None
    chroma_mod._chroma_store = None
    rag_mod._rag_service = None


@pytest.fixture(scope="session")
def session_env(tmp_path_factory):
    base = tmp_path_factory.mktemp("backend_tests")
    db_path = base / "test.db"
    chroma_path = base / "chroma"
    data_path = base / "complaints"
    data_path.mkdir()

    os.environ["DB_PATH"] = str(db_path)
    os.environ["DATABASE_URL"] = ""
    os.environ["CHROMA_PERSIST_DIR"] = str(chroma_path)
    os.environ["DATA_DIR"] = str(data_path)
    os.environ["REDIS_ENABLED"] = "false"
    os.environ["OPENAI_API_KEY"] = ""
    os.environ["RATE_LIMIT_ENABLED"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"

    _reset_singletons()

    from backend.app.database import init_db, seed_demo_user

    init_db()
    seed_demo_user()

    return {"db_path": db_path, "chroma_path": chroma_path, "data_path": data_path}


@pytest.fixture(scope="session")
def client(session_env):
    from backend.app.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture()
def test_env(session_env):
    _reset_singletons()
    yield session_env
