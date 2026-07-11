import json
import logging
from typing import Any, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from .cache import get_cache
from .chroma_store import get_chroma_store
from .config import get_settings
from .redis_client import get_redis

logger = logging.getLogger(__name__)

PROMPT_TEMPLATES = {
    "support": ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a customer support specialist. Use the retrieved complaint records to answer the user's question.\n"
                "Context:\n{context}\nAnswer clearly, empathetically, and with a concise action plan.",
            ),
            MessagesPlaceholder("history", optional=True),
            ("human", "{question}"),
        ]
    ),
    "manager": ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a support operations manager. Summarize the most likely resolution strategy and highlight the operational takeaway.\n"
                "Context:\n{context}\nProvide a concise executive summary.",
            ),
            MessagesPlaceholder("history", optional=True),
            ("human", "{question}"),
        ]
    ),
    "analyst": ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a complaint analysis specialist. Compare the retrieved complaints and explain recurring patterns.\n"
                "Context:\n{context}\nGive a short analytical summary.",
            ),
            MessagesPlaceholder("history", optional=True),
            ("human", "{question}"),
        ]
    ),
}


class ConversationMemory:
    """Redis-backed conversation memory per chat session."""

    def __init__(self, chat_id: int, max_messages: int = 20) -> None:
        self._redis = get_redis()
        self._settings = get_settings()
        self._chat_id = chat_id
        self._max_messages = max_messages
        self._key = f"chat_memory:{chat_id}"

    def get_history(self) -> list[dict[str, str]]:
        raw = self._redis.get(self._key)
        if not raw:
            return []
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []

    def add_message(self, role: str, content: str) -> None:
        history = self.get_history()
        history.append({"role": role, "content": content})
        history = history[-self._max_messages :]
        self._redis.set(self._key, json.dumps(history), ex=self._settings.session_ttl_seconds)

    def clear(self) -> None:
        self._redis.delete(self._key)

    def to_langchain_messages(self) -> list[tuple[str, str]]:
        return [(msg["role"], msg["content"]) for msg in self.get_history()]


class RAGChainService:
    """LangChain RAG pipeline with Chroma retriever and Redis caching."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._cache = get_cache()
        self._chroma = get_chroma_store()

    def list_templates(self) -> list[str]:
        return list(PROMPT_TEMPLATES.keys())

    def _format_docs(self, docs) -> str:
        return "\n\n".join(doc.page_content for doc in docs)

    def ask(
        self,
        question: str,
        template: str = "support",
        chat_id: Optional[int] = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        if template not in PROMPT_TEMPLATES:
            raise ValueError(f"Invalid template: {template}")

        if not self._settings.openai_api_key:
            docs = []
            try:
                if self._chroma.document_count() > 0 or self._settings.embeddings_provider == "local":
                    docs = self._chroma.similarity_search(question, k=3)
            except Exception as exc:
                logger.warning("Retrieval without OpenAI LLM failed: %s", exc)
            context = self._format_docs(docs) if docs else "No indexed complaints available."
            return {
                "answer": (
                    "OpenAI API key is not configured. Retrieved context:\n\n" + context
                    if docs
                    else "OpenAI API key is not configured. Add OPENAI_API_KEY to use the LLM-powered answer."
                ),
                "sources": [doc.metadata.get("source", "unknown") for doc in docs],
                "cached": False,
            }

        cache_key = self._cache.hash_key("rag", question, template, str(chat_id or ""))
        if use_cache:
            cached = self._cache.get("rag", cache_key)
            if cached:
                logger.info("RAG cache hit for template=%s", template)
                return {**cached, "cached": True}

        memory = ConversationMemory(chat_id) if chat_id else None
        history = memory.to_langchain_messages() if memory else []

        retriever = self._chroma.get_retriever(k=5)
        relevant_docs = retriever.invoke(question)
        context = self._format_docs(relevant_docs)

        llm = ChatOpenAI(
            model=self._settings.openai_model,
            openai_api_key=self._settings.openai_api_key,
            temperature=0.2,
        )
        prompt = PROMPT_TEMPLATES[template]
        chain = prompt | llm | StrOutputParser()
        answer = chain.invoke({"question": question, "context": context, "history": history})

        sources = [doc.metadata.get("source", "unknown") for doc in relevant_docs]
        result = {"answer": answer, "sources": sources, "cached": False}

        if use_cache:
            self._cache.set(
                "rag",
                cache_key,
                {"answer": answer, "sources": sources},
                ttl=self._settings.rag_cache_ttl_seconds,
            )

        if memory:
            memory.add_message("user", question)
            memory.add_message("assistant", answer)

        return result


_rag_service: Optional[RAGChainService] = None


def get_rag_service() -> RAGChainService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGChainService()
    return _rag_service
