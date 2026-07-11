import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import get_db, init_db, seed_demo_user
from .redis_client import get_redis
from .routers import auth, chats, rag, sessions, users

logger = logging.getLogger(__name__)
settings = get_settings()


def _configure_langsmith() -> None:
    if settings.langchain_tracing_v2:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        if settings.langchain_api_key:
            os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        logger.info("LangSmith tracing enabled for project %s", settings.langchain_project)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    _configure_langsmith()

    init_db()
    seed_demo_user()
    redis = get_redis()
    logger.info("Redis backend: %s (available=%s)", redis.backend, redis.is_redis_available)
    logger.info("Database backend: %s", get_db().backend)

    try:
        from .chroma_store import get_chroma_store

        store = get_chroma_store()
        if settings.openai_api_key or settings.embeddings_provider == "local":
            count = store.ensure_indexed()
            logger.info("ChromaDB indexed %s documents", count)
        else:
            logger.warning("No embeddings provider configured; ChromaDB indexing skipped")
    except Exception as exc:
        logger.warning("ChromaDB startup indexing skipped: %s", exc)

    yield
    logger.info("Shutting down Complaint RAG API")


app = FastAPI(
    title="Buiild Complaint RAG",
    description="Production complaint retrieval-augmented generation platform",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(users.router)
app.include_router(rag.router)
app.include_router(chats.router)


@app.get("/health")
def health() -> dict[str, Any]:
    redis = get_redis()
    doc_count = 0
    try:
        from .chroma_store import get_chroma_store

        doc_count = get_chroma_store().document_count()
    except Exception:
        pass
    return {
        "status": "ok",
        "redis": redis.backend,
        "redis_available": redis.is_redis_available,
        "database": get_db().backend,
        "chroma_collection": settings.chroma_collection,
        "chroma_documents": doc_count,
        "openai_configured": bool(settings.openai_api_key),
    }
