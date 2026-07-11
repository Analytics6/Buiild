import json
import logging
from pathlib import Path
from typing import Any, List, Optional

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from .cache import cached, get_cache
from .config import get_settings

logger = logging.getLogger(__name__)

TOPIC_KEYWORDS = {
    "billing": ["billing", "invoice", "charge", "overcharge", "payment"],
    "delivery": ["delivery", "shipment", "shipping", "delay", "tracking"],
    "product": ["product", "defective", "warranty", "broken", "damaged"],
    "subscription": ["subscription", "cancel", "cancellation", "plan"],
    "support": ["support", "response", "escalat", "wait time"],
    "refund": ["refund", "credit", "reimburse"],
}


def infer_topic(text: str) -> str:
    lowered = text.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return topic
    return "general"


def build_demo_dataset(count: int = 200) -> List[dict[str, Any]]:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.complaint_dataset import build_complaint_records

    return build_complaint_records(count)


def seed_demo_data(data_dir: Path, force: bool = False) -> None:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.complaint_dataset import write_complaint_files

    data_dir.mkdir(parents=True, exist_ok=True)
    write_complaint_files(data_dir, count=200, force=force or not any(data_dir.glob("*.json")))


def _document_from_item(item: dict[str, Any], source: str, path: str, idx: int) -> Optional[Document]:
    complaint = item.get("complaint") or item.get("issue") or item.get("description") or ""
    solution = item.get("solution") or item.get("resolution") or item.get("answer") or ""
    if not complaint:
        return None
    topic = item.get("topic") or infer_topic(f"{complaint} {solution}")
    return Document(
        page_content=f"Complaint: {complaint}\nSolution: {solution}",
        metadata={"source": source, "path": path, "index": idx, "topic": topic},
    )


def load_documents_from_json(data_dir: Path) -> List[Document]:
    seed_demo_data(data_dir)
    docs: List[Document] = []
    for path in sorted(data_dir.rglob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue
        if isinstance(payload, dict):
            payload = [payload]
        for idx, item in enumerate(payload):
            doc = _document_from_item(item, path.name, str(path), idx)
            if doc:
                docs.append(doc)
    return docs


class ChromaStore:
    """Persistent ChromaDB vector store via langchain-chroma."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._cache = get_cache()
        self._vectorstore = None
        self._embeddings = None

    def _get_embeddings(self):
        if self._embeddings is not None:
            return self._embeddings

        if self._settings.embeddings_provider == "local":
            from langchain_community.embeddings import HuggingFaceEmbeddings

            self._embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
            logger.info("Using local HuggingFace embeddings")
            return self._embeddings

        if not self._settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for embeddings")
        self._embeddings = OpenAIEmbeddings(openai_api_key=self._settings.openai_api_key)
        return self._embeddings

    def _get_vectorstore(self):
        if self._vectorstore is not None:
            return self._vectorstore

        from langchain_chroma import Chroma

        self._settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self._vectorstore = Chroma(
            collection_name=self._settings.chroma_collection,
            embedding_function=self._get_embeddings(),
            persist_directory=str(self._settings.chroma_persist_dir),
        )
        return self._vectorstore

    def document_count(self) -> int:
        try:
            store = self._get_vectorstore()
            return store._collection.count()
        except Exception:
            return 0

    def ensure_indexed(self, force_reindex: bool = False) -> int:
        docs = load_documents_from_json(self._settings.data_dir)
        if not docs:
            return 0

        if force_reindex or self.document_count() == 0:
            return self.index_documents(docs, replace=force_reindex)
        return self.document_count()

    def reset_collection(self) -> None:
        from langchain_chroma import Chroma

        self._settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self._vectorstore = Chroma(
            collection_name=self._settings.chroma_collection,
            embedding_function=self._get_embeddings(),
            persist_directory=str(self._settings.chroma_persist_dir),
        )
        try:
            self._vectorstore.delete_collection()
        except Exception:
            pass
        self._vectorstore = None
        self._cache.delete("chroma", "doc_count")

    def index_documents(self, documents: List[Document], replace: bool = False) -> int:
        if not documents:
            return 0

        from langchain_chroma import Chroma

        self._settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        embeddings = self._get_embeddings()

        if replace or self.document_count() == 0:
            if replace and self.document_count() > 0:
                self.reset_collection()
            self._vectorstore = Chroma.from_documents(
                documents=documents,
                embedding=embeddings,
                collection_name=self._settings.chroma_collection,
                persist_directory=str(self._settings.chroma_persist_dir),
            )
        else:
            store = self._get_vectorstore()
            store.add_documents(documents)

        self._cache.delete("chroma", "doc_count")
        return self.document_count()

    def add_documents_from_payload(self, payload: list[dict[str, Any]], source: str) -> int:
        documents: List[Document] = []
        for idx, item in enumerate(payload):
            doc = _document_from_item(item, source, source, idx)
            if doc:
                documents.append(doc)
        if not documents:
            return 0
        return self.index_documents(documents)

    def get_retriever(self, k: int = 5):
        store = self._get_vectorstore()
        if self.document_count() == 0:
            self.ensure_indexed()
        return store.as_retriever(search_kwargs={"k": k})

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        cache_key = self._cache.hash_key("embed_search", query, str(k))
        cached = self._cache.get("embeddings", cache_key)
        if cached:
            return [
                Document(page_content=item["page_content"], metadata=item.get("metadata", {}))
                for item in cached
            ]

        store = self._get_vectorstore()
        if self.document_count() == 0:
            self.ensure_indexed()
        results = store.similarity_search(query, k=k)
        self._cache.set(
            "embeddings",
            cache_key,
            [{"page_content": d.page_content, "metadata": d.metadata} for d in results],
            ttl=self._settings.embedding_cache_ttl_seconds,
        )
        return results


_chroma_store: Optional[ChromaStore] = None


def get_chroma_store() -> ChromaStore:
    global _chroma_store
    if _chroma_store is None:
        _chroma_store = ChromaStore()
    return _chroma_store
