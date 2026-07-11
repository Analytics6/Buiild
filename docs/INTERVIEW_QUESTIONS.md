# Buiild Complaint RAG — Interview Preparation Guide

> **30 scenario-based interview questions** with detailed answers grounded in the actual Buiild Complaint RAG codebase (FastAPI, Redis, ChromaDB, LangChain, SQLite/PostgreSQL, React).

**Difficulty mix:** 8 junior · 12 mid · 10 senior

---

## Table of Contents

1. [System Design & Architecture](#system-design--architecture) (Q1–Q5)
2. [RAG Pipeline & LangChain](#rag-pipeline--langchain) (Q6–Q10)
3. [Authentication, Sessions & Redis](#authentication-sessions--redis) (Q11–Q14)
4. [ChromaDB & Vector Search](#chromadb--vector-search) (Q15–Q17)
5. [Caching & Performance](#caching--performance) (Q18–Q20)
6. [Production Scaling & DevOps](#production-scaling--devops) (Q21–Q24)
7. [Testing & Evaluation](#testing--evaluation) (Q25–Q26)
8. [Troubleshooting Scenarios](#troubleshooting-scenarios) (Q27–Q28)
9. [Frontend & API Design](#frontend--api-design) (Q29–Q30)

---

## System Design & Architecture

### Q1. Explaining the Platform to a New Teammate
**Scenario:** You join the Buiild Complaint RAG team on day one. Your onboarding buddy asks you to whiteboard what the system does and which major components talk to each other.
**Question:** Walk me through the high-level architecture of this complaint RAG platform.
**Answer:** I'd describe Buiild Complaint RAG as a production-oriented RAG platform for customer complaint intelligence. The React frontend (Support Operations Console in `frontend/src/App.jsx`) talks to a FastAPI backend on port 8000. The backend is organized into thin routers (`backend/app/routers/`) and service layers — `RAGChainService` in `rag_chain.py`, `ChromaStore` in `chroma_store.py`, `SessionService` in `sessions.py`, and `UserService` in `users.py`.

Data flows through three persistence tiers: SQLite or PostgreSQL for durable users/chats/sessions audit (`database.py`), Redis for hot-path state (sessions, RAG cache, embedding cache, chat memory, rate limits), and ChromaDB on disk at `data/chroma/` for vector search over complaint JSON in `data/complaints/`. AI calls go to OpenAI for chat (`ChatOpenAI` in `rag_chain.py`) and embeddings (default `OpenAIEmbeddings` in `chroma_store.py`), with a local HuggingFace fallback (`all-MiniLM-L6-v2`) when `EMBEDDINGS_PROVIDER=local`.

On startup, `main.py` lifespan runs `init_db()`, seeds demo users, connects Redis (or falls back to in-memory), and calls `ensure_indexed()` to populate Chroma if empty. The legacy Streamlit app (`app.py`) and TF-IDF RAG (`src/complaint_rag.py`) exist separately — the production path is LangChain + Chroma.

**Key points:**
- FastAPI backend + React SPA + Redis + ChromaDB + SQLite/PostgreSQL
- Routers delegate to services; no business logic in HTTP handlers
- Complaint JSON files are the corpus; Chroma is the search index
- Legacy TF-IDF path is separate from production LangChain pipeline

---

### Q2. Choosing FastAPI for the API Layer
**Scenario:** During a design review, a teammate familiar with Django asks why this project uses FastAPI instead of a batteries-included framework.
**Question:** Why is FastAPI a good fit for this complaint RAG API, and what trade-offs did we accept?
**Answer:** FastAPI fits this project because the workload is API-heavy with clear request/response contracts and async-friendly I/O boundaries, even though the RAG chain itself is currently synchronous (`chain.invoke()` in `rag_chain.py`). Pydantic models in `schemas.py` give us validated `AskRequest`, `AskResponse`, and auth payloads with automatic OpenAPI docs at `/docs` — valuable for a platform with ~20 endpoints spanning auth, sessions, RAG, and chats.

The lifespan hook in `main.py` cleanly orchestrates startup: LangSmith tracing config, DB init, Redis connection, and Chroma indexing. FastAPI's dependency injection (`dependencies.py`) composes auth (`get_current_user`), RBAC (`require_roles`), and rate limiting (`rate_limit("ask")`) without middleware spaghetti.

The trade-off is that FastAPI doesn't ship an ORM or admin panel — we wrote a thin SQL abstraction in `database.py` for SQLite/PostgreSQL. That's acceptable for an MVP with four tables, but we'd likely add SQLAlchemy or an async driver layer before heavy schema evolution. Another trade-off: sync LLM calls block a worker thread; production scaling docs recommend gunicorn multi-worker or async job queues for `/ask`.

**Key points:**
- Pydantic validation + auto-generated OpenAPI
- Dependency injection for auth, RBAC, rate limits
- Lifespan hook for startup orchestration
- Trade-off: no built-in ORM; sync RAG blocks workers

---

### Q3. End-to-End Request Flow for a RAG Query
**Scenario:** In a system design interview, you're asked to trace a single `/ask` request from the browser through to the LLM response.
**Question:** Describe the complete data flow when a logged-in support agent asks, "How do we handle billing overcharges?"
**Answer:** Starting in the React assistant view (`App.jsx`), `askQuestion()` POSTs to `/api/ask` with `{ question, template, chat_id }` and a Bearer token from `localStorage` (`complaint-token`). Vite's proxy rewrites `/api/ask` → `http://127.0.0.1:8002/ask` (note: port must match the running backend).

FastAPI's `rag.py` router invokes `rate_limit("ask")` which calls `get_current_user` → `resolve_user_from_token()` in `auth.py`. Session validation checks Redis `session:{token}` first; on miss, DB rehydration in `sessions.py`. The rate limiter (`cache.py`) increments `ratelimit:{user_id}:ask:{bucket}`.

`RAGChainService.ask()` hashes `question|template|chat_id` → `cache:rag:{hash}`. On cache miss, if `chat_id` is set, `ConversationMemory` loads up to 20 messages from `chat_memory:{chat_id}`. The Chroma retriever fetches top-5 documents (`get_retriever(k=5)`). Context is formatted as concatenated `page_content` strings. The selected `PROMPT_TEMPLATES` entry assembles system + history + human messages. `ChatOpenAI` (default `gpt-4o-mini`, `temperature=0.2`) generates the answer via `prompt | llm | StrOutputParser()`.

The result is cached in Redis for `RAG_CACHE_TTL_SECONDS` (30 min default), chat memory is updated, and the response `{ answer, sources[], cached }` returns. The frontend then persists both messages to SQLite via `POST /chat/{id}/message`.

**Key points:**
- Auth → rate limit → cache check → memory → retrieval → LLM → cache store
- Dual chat persistence: Redis memory for RAG, SQLite for UI history
- Sources are filenames from Chroma metadata (`source` field)
- Default retriever k=5, temperature=0.2

---

### Q4. Source of Truth for Complaint Data
**Scenario:** Your team debates whether complaint records should live primarily in JSON files, PostgreSQL, or ChromaDB. A product manager wants a clear answer before adding a CRM integration.
**Question:** What is the source of truth for complaint data in this architecture, and how do the other stores relate?
**Answer:** The source of truth is the **filesystem** — specifically `data/complaints/*.json` (configurable via `DATA_DIR`). Each file contains complaint/solution pairs; the demo dataset generates 200 files via `src/complaint_dataset.py`. Uploads via `POST /upload` save to `data/complaints/{filename}/custom.json` and immediately index into Chroma.

ChromaDB at `data/chroma/` is a **derived search index** — embeddings of `page_content` ("Complaint: ...\nSolution: ...") plus metadata (`source`, `topic`, `path`, `index`). It can be fully rebuilt from JSON via `POST /reindex` or `scripts/reindex_chroma.py` using `index_documents(docs, replace=True)`.

SQLite/PostgreSQL stores **application state** — users, session audit rows, chats, messages — not the complaint corpus. This separation is intentional: complaint data is relatively static and bulk-loaded; app state is transactional.

For a CRM integration, I'd ingest CRM exports into `data/complaints/` (or a staging table), then trigger incremental or full reindex. I would not make Chroma the source of truth because it's not human-auditable and rebuilding from it alone would lose structured fields. PostgreSQL could become an intermediate store if we need queryable complaint metadata before indexing, but the current MVP keeps it simple.

**Key points:**
- JSON files in `DATA_DIR` are canonical
- Chroma is a rebuildable vector index
- SQL DB stores users/chats/sessions, not complaints
- Reindex rebuilds Chroma from JSON via `replace=True`

---

### Q5. Scaling from MVP to 10,000 Concurrent Users
**Scenario:** Leadership targets 10k concurrent users for the complaint intelligence platform. You're asked to present the current bottlenecks and a phased scaling plan.
**Question:** What are the primary scaling bottlenecks today, and what infrastructure changes would you prioritize?
**Answer:** Today this is a well-structured single-node MVP. The bottlenecks, documented in `PRODUCTION_SCALING.md`, are: (1) single uvicorn process in `Dockerfile.backend` — LLM latency blocks other requests; (2) SQLite default with per-request connections and write locks; (3) in-memory Redis fallback in `redis_client.py` that isolates sessions/cache per pod; (4) local Chroma on a shared volume — unsafe for multiple API replicas; (5) sync `chain.invoke()` with no circuit breaker; (6) `ensure_indexed()` on every pod startup causing index storms.

My phased plan: **Week 1 quick wins** — require Redis in production (fail fast, no in-memory fallback), migrate to PostgreSQL with connection pooling, switch to gunicorn with 4 `UvicornWorker` processes, split `/health/live` and `/health/ready`, fix rate limiter to use atomic Redis `INCR`, move indexing off startup to a one-time init job, rotate `JWT_SECRET` via secrets manager.

**Medium term** — Celery/RQ workers for upload/reindex, managed vector DB (Qdrant/Pinecone/Weaviate), K8s HPA with 3–50 pods, streaming `/ask`, OpenAI circuit breaker, CDN for frontend static assets, Prometheus metrics.

At 10k concurrent users with ~5–10% active on `/ask`, we estimate 500–1000 RPS peak on that endpoint. With 40% cache hit rate, that's still 300–600 LLM calls/minute — requiring 8–15 API replicas, Redis cluster, and async workers. The current architecture enables this path because services are already modular (`ChromaStore`, `CacheService`, `SessionService`).

**Key points:**
- Single worker + SQLite + local Chroma block horizontal scale
- Redis required for multi-replica session/cache consistency
- Quick wins: PostgreSQL, gunicorn, health probes, atomic rate limits
- Long term: managed vector DB, async workers, K8s HPA

---

## RAG Pipeline & LangChain

### Q6. How Retrieval Grounds the LLM Answer
**Scenario:** A junior support agent using the AI assistant asks, "How does the system know which past complaints to reference when I type a question?"
**Question:** Explain how retrieval works in the production RAG pipeline.
**Answer:** When a question hits `RAGChainService.ask()` in `rag_chain.py`, the system does not send the question directly to the LLM. Instead, it calls `self._chroma.get_retriever(k=5)` which performs similarity search over the ChromaDB `complaints` collection. Each indexed document has `page_content` formatted as `"Complaint: {text}\nSolution: {text}"` and metadata including `source` (filename), `topic`, and `path`.

Embeddings are computed at index time and query time. By default, `EMBEDDINGS_PROVIDER=openai` uses `OpenAIEmbeddings`; setting `local` switches to HuggingFace `all-MiniLM-L6-v2` in `chroma_store.py`. The retriever returns the top-5 most semantically similar complaint records. These are joined into a context string via `_format_docs()` and injected into the system prompt: `"Context:\n{context}"`.

The LLM (`ChatOpenAI`, default `gpt-4o-mini`) then generates an answer conditioned on that context — this is classic RAG, reducing hallucination by grounding responses in real resolution history. The response includes `sources[]` — filenames like `complaint_001.json` — so agents can verify provenance.

**Key points:**
- Chroma similarity search returns top-5 documents (k=5)
- Document format: Complaint + Solution in `page_content`
- Embeddings via OpenAI or local HuggingFace model
- Sources returned from metadata for attribution

---

### Q7. Role-Specific Prompt Templates
**Scenario:** Your product owner wants support agents, managers, and analysts to receive differently styled answers from the same underlying complaint data.
**Question:** How does the template system work, and how would you add a new template?
**Answer:** The platform exposes three templates via `PROMPT_TEMPLATES` in `rag_chain.py`: `support` (empathetic action plan), `manager` (executive summary with operational takeaway), and `analyst` (pattern comparison across complaints). Each is a `ChatPromptTemplate.from_messages` with a role-specific system prompt, an optional `MessagesPlaceholder("history")` for multi-turn context, and a human message slot for `{question}`.

The `/ask` endpoint accepts `template` in the request body (validated as `TemplateType` in `schemas.py`). The template name is part of the RAG cache key (`hash_key("rag", question, template, chat_id)`), so the same question with different templates produces different cached entries and different LLM outputs.

To add a new template — say `escalation` — I'd add an entry to `PROMPT_TEMPLATES`, extend `TemplateType = Literal[..., "escalation"]` in `schemas.py`, and it automatically appears in `GET /templates` via `list_templates()`. No router changes needed. I'd also add a pytest case for invalid template → 422, following `test_ask_invalid_template` in `tests/test_rag.py`.

**Key points:**
- Three built-in personas: support, manager, analyst
- Template affects system prompt and cache key
- Add via `PROMPT_TEMPLATES` dict + `schemas.py` Literal type
- `GET /templates` lists available templates (no auth required)

---

### Q8. Multi-Turn Conversation Context
**Scenario:** A support agent starts a chat, asks about a billing issue, then follows up with "What refund amount was typically offered?" The second answer ignores the first exchange.
**Question:** How does conversation memory work, and what could cause follow-up questions to lose context?
**Answer:** Multi-turn context is handled by `ConversationMemory` in `rag_chain.py`. When `/ask` receives a `chat_id`, the service loads up to 20 prior messages from Redis key `chat_memory:{chat_id}` and passes them to the LangChain `MessagesPlaceholder("history")`. After each successful answer, both the user question and assistant response are appended.

Several things could cause context loss: (1) **missing `chat_id`** — if the frontend doesn't pass it, memory is skipped entirely; (2) **RAG cache hit** — the cache key includes `chat_id`, but if the same question was cached from a different chat or without `chat_id`, you'd get a stale answer (unlikely for follow-ups with different wording); (3) **Redis TTL expiry** — memory uses `SESSION_TTL_SECONDS` (24h); after expiry, history is gone though SQLite messages remain; (4) **frontend not creating a chat** — `askQuestion()` in `App.jsx` requires `chatId` before calling `/ask`.

Notably, chat history exists in **two places**: Redis `chat_memory` (for RAG context) and SQLite `messages` table (for UI display via `/chat/{id}/messages`). Deleting a chat removes DB records but does not explicitly clear Redis memory — a known gap where TTL handles cleanup. For production, I'd add explicit `memory.clear()` on chat delete and consider including a hash of recent history in the cache key more aggressively.

**Key points:**
- Redis `chat_memory:{chat_id}` stores last 20 messages
- `chat_id` must be passed to `/ask` for memory
- Dual persistence: Redis for RAG, SQLite for UI
- Chat delete doesn't clear Redis memory (TTL-based cleanup)

---

### Q9. Debugging RAG Quality with LangSmith
**Scenario:** You're on-call in staging with `LANGCHAIN_TRACING_V2=true`. Users report that answers about delivery complaints cite billing cases instead.
**Question:** How would you debug a retrieval quality issue using the project's observability tooling?
**Answer:** With LangSmith enabled via `main.py` `_configure_langsmith()`, each LangChain invocation in the RAG pipeline generates traces showing retriever calls, prompt assembly, and LLM output. I'd start by finding a failing `/ask` trace and checking the **retriever step** — which 5 documents were returned for the delivery question? If billing docs rank higher, the issue is embedding similarity, not generation.

Next, I'd inspect **indexed content** in Chroma. Documents are built by `_document_from_item()` with topic inferred via keyword matching (`infer_topic()` in `chroma_store.py`). If delivery complaints were mis-tagged as `billing`, metadata filtering could help — though the current retriever doesn't filter by topic, it's pure similarity search.

I'd compare **embedding providers** — OpenAI ada-002 vs local MiniLM produce different vector spaces. Mixed providers between index and query would catastrophically degrade retrieval. I'd verify `EMBEDDINGS_PROVIDER` hasn't changed since indexing.

Remediation paths: (1) reindex with `POST /reindex` after fixing data; (2) increase k or add metadata filters; (3) implement hybrid search (BM25 + vector) per the production roadmap; (4) add retrieval evaluators like the notebook's `retrieval_relevance_evaluator`. For immediate mitigation, I'd lower temperature or add topic hints to the system prompt — but fixing retrieval at the source is the durable fix.

**Key points:**
- LangSmith traces retriever, prompt, and LLM steps
- Check top-5 retrieved docs and their metadata topics
- Embedding provider must be consistent at index and query time
- Notebook evaluators (`retrieval_relevance_evaluator`) test retrieval quality

---

### Q10. Operating Without an OpenAI API Key
**Scenario:** A developer clones the repo for a code review but doesn't have an OpenAI API key. They want to run the backend and tests locally.
**Question:** What happens when `OPENAI_API_KEY` is empty, and how can developers still work on the project?
**Answer:** The project is designed for graceful degradation. In `rag_chain.py`, if `openai_api_key` is empty, the service skips the LLM chain entirely and attempts retrieval-only mode: it calls `similarity_search(question, k=3)` (note: k=3 here, not 5) and returns either the raw retrieved context prefixed with "OpenAI API key is not configured" or a message asking to configure the key.

For embeddings, `chroma_store.py` raises `ValueError` if provider is `openai` and no key is set. Setting `EMBEDDINGS_PROVIDER=local` enables HuggingFace `all-MiniLM-L6-v2` — no API cost, though the model downloads on first use. Startup indexing in `main.py` runs when either `openai_api_key` is set **or** `embeddings_provider == "local"`.

The pytest suite in `conftest.py` sets `OPENAI_API_KEY=""` and `REDIS_ENABLED=false`, so all tests pass without external services. `test_ask_without_openai_key` in `tests/test_rag.py` verifies `/ask` returns 200 with retrieval-only content. This lets developers work on auth, sessions, caching, and Chroma indexing without LLM access.

**Key points:**
- No OpenAI key → retrieval-only `/ask` responses
- `EMBEDDINGS_PROVIDER=local` enables offline embeddings
- Tests disable OpenAI and Redis by default in `conftest.py`
- LLM generation requires `OPENAI_API_KEY`; retrieval can work without it

---

## Authentication, Sessions & Redis

### Q11. Session Loss After Redis Restart
**Scenario:** A customer reports that all users were logged out after an overnight Redis maintenance window. The backend logs show `redis_available: false` briefly, then recovery.
**Question:** Why did users lose their sessions, and how does the system recover?
**Answer:** Session tokens are stored primarily in Redis under `session:{token}` with a TTL of `SESSION_TTL_SECONDS` (default 24 hours). `SessionService.create_session()` in `sessions.py` generates a 32-byte URL-safe token via `secrets.token_urlsafe(32)`, stores the payload in Redis, adds it to `user:{id}:sessions` set, and inserts an audit row in the SQL `sessions` table.

When Redis restarts without AOF/RDB persistence, all session keys are lost. Users' browsers still hold tokens in `localStorage` (`complaint-token`), but `validate_session()` finds no Redis key. The system then **falls back to the database**: it queries `sessions WHERE token = ? AND revoked = 0` and, if found, **rehydrates** the Redis key. So users should recover automatically unless the session was expired/revoked in DB.

If Redis was unavailable and the app used the **in-memory fallback** (`InMemoryStore` in `redis_client.py`), each process has isolated storage — a user validated on pod A fails on pod B. Docker Compose does enable Redis AOF persistence (`redis_data` volume), which prevents this in normal ops.

I'd recommend: enable Redis persistence, require Redis in production (fail fast instead of in-memory fallback), and monitor `/health` for `redis_available`. The dual-store design (Redis hot + SQL audit) is specifically for this rehydration path.

**Key points:**
- Sessions live in Redis `session:{token}` with SQL audit backup
- DB rehydration on Redis cache miss if `revoked=0`
- In-memory fallback breaks multi-replica consistency
- Redis AOF persistence is enabled in Docker Compose

---

### Q12. JWT Bypasses Session Revocation
**Scenario:** During a security review, an auditor logs out, then replays the old JWT token and still gets authenticated.
**Question:** Explain the dual auth model and the security gap around JWT fallback.
**Answer:** On login, the API returns two credentials: a **session token** (opaque, stored in Redis) and a **JWT** (signed HS256, stateless). `resolve_user_from_token()` in `auth.py` tries session validation first via `SessionService.validate_session()`, then falls back to `decode_jwt_token()` and a DB user lookup.

Session tokens are fully revocable — `POST /logout` deletes the Redis key, removes from the user set, and sets `revoked=1` in SQL. JWTs are **not** revocable in the current implementation. They remain valid until `exp` (default `JWT_EXPIRE_MINUTES=1440`, 24 hours). The frontend stores only the session token in `localStorage`, not the JWT, which mitigates the risk for normal UI usage. But any client that saved the JWT can bypass logout.

For production, `PRODUCTION_SCALING.md` recommends: prefer session-only auth, disable JWT fallback, or use very short JWT TTL with a refresh flow. I'd implement a `jwt_denylist` in Redis for logout, or simply remove the JWT fallback from `resolve_user_from_token()` since the React app doesn't use it. The JWT was likely added for stateless API consumers or future mobile clients — but it needs a revocation strategy before production.

**Key points:**
- Session tokens are revocable; JWTs are not
- `resolve_user_from_token()` falls back to JWT after session miss
- Frontend uses session token only (`complaint-token`)
- Production fix: disable JWT fallback or add denylist

---

### Q13. Revoking a Compromised Session Across Devices
**Scenario:** A support manager's account may be compromised. Security asks you to revoke all active sessions except the current one.
**Question:** How does multi-device session management work in this project?
**Answer:** Each login creates an independent session token. `SessionService.create_session()` stores each in Redis `session:{token}` and adds it to the set `user:{user_id}:sessions`. An audit row is inserted in the SQL `sessions` table with `user_agent` and `ip_address` for forensics.

`GET /sessions` lists active sessions with `token_preview` (truncated), created_at, user agent, and IP. `DELETE /sessions/{session_id}` revokes a specific session by its **database ID** — it deletes the Redis key, removes from the user set, and marks `revoked=1` in SQL. `POST /logout` revokes only the current session token.

For "revoke all except current," the current codebase doesn't have a bulk-revoke endpoint — I'd iterate `GET /sessions` and call `DELETE /sessions/{id}` for each except the active one, or add an admin endpoint that calls `SessionService.revoke_all_sessions(user_id, except_token=current)`. The Redis set `user:{id}:sessions` makes this efficient — `SMEMBERS` then bulk delete.

The `POST /sessions/refresh` endpoint extends TTL on the current token via Redis `EXPIRE`, useful for long dashboard sessions without re-login.

**Key points:**
- Each login creates independent Redis session + DB audit row
- `user:{id}:sessions` set tracks all tokens per user
- Revoke via `DELETE /sessions/{id}` or `POST /logout`
- No bulk-revoke endpoint yet — would need to be added

---

### Q14. Why Redis Is Mandatory for Multi-Replica Deployments
**Scenario:** You're deploying four FastAPI replicas behind a load balancer. A colleague suggests running without Redis to simplify infrastructure.
**Question:** Why would removing Redis break the application at scale?
**Answer:** Redis serves five critical functions that must be **shared** across all API replicas: (1) **session storage** — without shared Redis, a user logging in on replica A fails auth on replica B; (2) **RAG answer cache** — each pod would have its own cache in the in-memory fallback, reducing hit rate to ~1/N; (3) **embedding search cache** — same problem, more Chroma round-trips; (4) **chat memory** — multi-turn context would be lost when the next request hits a different pod; (5) **rate limiting** — per-user counters would be isolated, effectively multiplying the rate limit by N.

The `redis_client.py` in-memory fallback (`InMemoryStore`) is a dev convenience with a thread-safe `RLock`, but it's per-process. `PRODUCTION_SCALING.md` explicitly recommends requiring Redis in production and failing fast if unavailable rather than silently falling back.

With Redis (or Redis Cluster/ElastiCache at scale), all replicas share state with O(1) lookups. Session rehydration from SQL provides durability, but Redis is the hot path for every authenticated request. I'd also fix the rate limiter's non-atomic read-modify-write in `cache.py` to use Redis `INCR` before going multi-replica.

**Key points:**
- Redis shares sessions, caches, memory, and rate limits across pods
- In-memory fallback is per-process — breaks load-balanced deploys
- Production should fail fast if Redis is unavailable
- Rate limiter needs atomic `INCR` for correctness under concurrency

---

## ChromaDB & Vector Search

### Q15. Stale Answers After Uploading New Complaints
**Scenario:** A support lead uploads 50 new billing complaint JSON files via the Knowledge Base UI. Agents still receive old answers about billing policies for the next 20 minutes.
**Question:** Why don't uploaded complaints immediately affect RAG answers, and how do you fix it?
**Answer:** Upload via `POST /upload` in `rag.py` does two things: saves JSON to `data/complaints/{filename}/custom.json` and calls `add_documents_from_payload()` which appends new documents to the Chroma collection via `index_documents()`. So **retrieval should include new documents immediately** on cache miss.

The stale answers are almost certainly caused by the **RAG answer cache** in Redis. `RAGChainService.ask()` caches results under `cache:rag:{hash(question, template, chat_id)}` with `RAG_CACHE_TTL_SECONDS` (default 1800s / 30 min). Upload does **not** invalidate existing RAG cache entries — a known gap documented in `ARCHITECTURE.md` and `PRODUCTION_SCALING.md`.

Fixes: (1) call `POST /reindex` which rebuilds the index and clears `cache:chroma:doc_count` (though RAG cache keys remain); (2) wait for TTL expiry; (3) pass `use_cache: false` in the `/ask` request; (4) implement cache namespace invalidation — e.g., increment a corpus version in the cache key prefix on upload. The embedding cache (`cache:embeddings:{hash}`) has a similar TTL (24h) but is cleared on reindex via `reset_collection()`.

For an interview, I'd emphasize: indexing is incremental and works; the gap is cache invalidation strategy, not retrieval itself.

**Key points:**
- Upload appends to Chroma immediately via `add_documents_from_payload()`
- RAG answer cache (30 min TTL) is NOT invalidated on upload
- Workarounds: `use_cache: false`, `/reindex`, or wait for TTL
- Production fix: corpus version prefix or namespace invalidation

---

### Q16. Document Structure in the Vector Index
**Scenario:** You're onboarding a data engineer who will prepare complaint JSON files for indexing. They ask what format the vector database expects.
**Question:** How are complaint records transformed into ChromaDB documents?
**Answer:** The indexer in `chroma_store.py` reads all `*.json` files recursively from `DATA_DIR`. Each file can be a single object or an array. `_document_from_item()` extracts fields with flexible aliases: `complaint` / `issue` / `description` for the issue text, and `solution` / `resolution` / `answer` for the resolution. Records without a complaint field are skipped.

The `page_content` stored in Chroma is: `"Complaint: {complaint}\nSolution: {solution}"`. Metadata includes: `source` (filename like `complaint_001.json`), `path` (absolute file path), `index` (position in array), and `topic` (explicit field or inferred via `infer_topic()` keyword matching against families like billing, delivery, product, subscription, support, refund, or `general`).

The collection name defaults to `complaints` (`CHROMA_COLLECTION`), persisted at `CHROMA_PERSIST_DIR` (default `./data/chroma`). Embeddings are computed by `OpenAIEmbeddings` or local HuggingFace at index time. On first startup with an empty collection, `ensure_indexed()` in `main.py` loads all JSON and calls `index_documents()`. The demo seeder generates 200 detailed records if the directory is empty.

**Key points:**
- Flexible JSON field aliases (complaint/issue, solution/resolution)
- `page_content` = Complaint + Solution text combined
- Metadata: source, path, index, topic
- Topic inferred by keyword matching if not provided

---

### Q17. Migrating from Local ChromaDB to a Managed Vector Database
**Scenario:** Your team decides to replace local ChromaDB with Pinecone before scaling to Kubernetes. You're asked to scope the migration.
**Question:** What would need to change in the codebase, and what are the trade-offs?
**Answer:** The good news is that retrieval is already abstracted behind `ChromaStore` in `chroma_store.py` with a clean interface: `index_documents()`, `add_documents_from_payload()`, `similarity_search()`, `get_retriever()`, `document_count()`, `ensure_indexed()`, and `reset_collection()`. The RAG pipeline in `rag_chain.py` only calls `get_retriever(k=5)` and never touches Chroma directly.

Migration approach: create a `VectorStore` protocol or base class, implement `PineconeStore` (or Qdrant/Weaviate per `PRODUCTION_SCALING.md`), and swap the singleton in `get_chroma_store()`. Key changes: (1) replace `langchain_chroma.Chroma` with `langchain_pinecone` or a custom retriever; (2) move `CHROMA_PERSIST_DIR` to `VECTOR_DB_URL` + API key env vars; (3) remove local disk volume mounts from Docker/K8s; (4) migrate embedding pipeline — re-embed all 200+ documents into Pinecone; (5) update `/health` and readiness probes to check remote vector DB connectivity.

Trade-offs: Pinecone eliminates file corruption from multi-replica mounts and enables horizontal scaling, but adds cost, network latency, and vendor dependency. Local Chroma is free and simple for MVP but cannot scale beyond one writer. The `ensure_indexed()` startup hook must be removed either way — indexing should be an async worker job. I'd keep the `ChromaStore` filename temporarily and alias it, minimizing router and test changes.

**Key points:**
- `ChromaStore` is the single abstraction point for migration
- `rag_chain.py` depends on retriever interface, not Chroma directly
- Remove shared volume mounts; add remote DB health checks
- Indexing must move off startup to async workers

---

## Caching & Performance

### Q18. Understanding RAG Cache Hits
**Scenario:** A developer notices the second identical question in the assistant returns `"cached": true` almost instantly, while the first took 4 seconds.
**Question:** Explain the RAG caching layer and when cache hits occur.
**Answer:** `RAGChainService.ask()` implements cache-aside pattern via `CacheService` in `cache.py`. Before retrieval or LLM calls, it computes `cache_key = hash_key("rag", question, template, str(chat_id or ""))` — a SHA-256 hash truncated to 32 chars. It checks Redis key `cache:rag:{hash}`. On hit with `use_cache=true`, it returns the stored `{answer, sources}` immediately with `cached: true`.

On miss, the full pipeline runs (retrieval → LLM → store). The result is saved with TTL `RAG_CACHE_TTL_SECONDS` (default 1800 / 30 min). The `use_cache` field in `AskRequest` defaults to `true`; setting it `false` bypasses both read and write.

There's also a separate **embedding cache** at `cache:embeddings:{hash(query, k)}` with 24h TTL in `similarity_search()` — this avoids repeated Chroma round-trips for identical queries but is transparent to the `/ask` response's `cached` flag (which only reflects RAG answer cache).

For production, `PRODUCTION_SCALING.md` recommends increasing RAG cache TTL to 1–4 hours since complaint data changes infrequently, potentially saving 40–60% of LLM calls.

**Key points:**
- Cache key = SHA-256 of question + template + chat_id
- TTL default 30 min (`RAG_CACHE_TTL_SECONDS`)
- `cached: true` in response means RAG answer cache hit
- Separate embedding cache with 24h TTL

---

### Q19. Rate Limit Exceeded During a Live Demo
**Scenario:** During a stakeholder demo, the presenter rapidly asks 80 questions in one minute. The UI shows "Rate limit exceeded" errors.
**Question:** How does rate limiting work on `/ask`, and what are your options during a demo?
**Answer:** The `/ask` endpoint uses `Depends(rate_limit("ask"))` from `dependencies.py`. `RateLimiter.is_allowed()` in `cache.py` implements a sliding window per user per endpoint. It computes `bucket = now // window_seconds` (default window = 60s) and tracks count in Redis key `ratelimit:{user_id}:ask:{bucket}`. Default limit is `RATE_LIMIT_REQUESTS=60` per window. When count >= limit, it returns False and FastAPI raises HTTP 429.

For a demo, options include: (1) set `RATE_LIMIT_ENABLED=false` in `.env` (what the test suite does); (2) increase `RATE_LIMIT_REQUESTS=120`; (3) rely on RAG caching — repeated questions don't count as less work but still increment the counter; (4) use multiple demo accounts to distribute load. Note: the current implementation uses non-atomic read-modify-write (`get` then `set`), which can slightly under-count under concurrency — a production fix is Redis `INCR`.

The rate limit only applies to `/ask`, not to auth, chat, or upload endpoints. An API gateway edge rate limiter is recommended for production per `PRODUCTION_SCALING.md`.

**Key points:**
- 60 requests/minute/user default on `/ask` only
- Sliding window via time-bucketed Redis counter
- Disable via `RATE_LIMIT_ENABLED=false` for demos
- Production fix: atomic Redis `INCR` instead of get/set

---

### Q20. Low Cache Hit Ratio Despite Repeated FAQ Questions
**Scenario:** In production, you observe that agents ask the same 20 FAQ questions repeatedly, but the RAG cache hit ratio is near 0%. You need to diagnose and improve it.
**Answer:** I'd investigate several cache-key variables that prevent hits. First, **`chat_id` in the cache key** — `hash_key("rag", question, template, str(chat_id))` means the same question in different chats produces different keys. If every conversation creates a new chat (as `App.jsx` does with "New case review"), FAQ-style identical questions never hit cache. Fix: for organization-wide FAQs, either omit `chat_id` from the cache key when history isn't needed, or add a separate cache tier for `chat_id=none`.

Second, **template variation** — the same question with `support` vs `manager` template is a cache miss. That's intentional but reduces hit rate in mixed-role environments.

Third, **question normalization** — `payload.question.strip()` handles whitespace, but case differences ("Billing" vs "billing") or trailing punctuation create different hashes. Adding lowercase normalization or semantic caching (embedding similarity of questions) could improve hits by 15–25% per the scaling guide.

Fourth, **TTL too short** — 30 min may expire between shift changes. Increasing to 1–4 hours is recommended for stable complaint corpora.

Fifth, **`use_cache: false`** — check if any client explicitly disables caching.

I'd add a `rag_cache_hit_ratio` Prometheus metric, normalize questions before hashing, and consider a two-tier key: `rag:faq:{hash(question, template)}` for cache lookup before the chat-specific key.

**Key points:**
- `chat_id` in cache key prevents cross-chat FAQ hits
- Template and question text variations cause misses
- Normalize questions; consider longer TTL (1–4 hr)
- Semantic caching is a future optimization

---

## Production Scaling & DevOps

### Q21. Kubernetes Readiness Probe Failing on Deploy
**Scenario:** You add `/health/ready` per the scaling guide. New pods fail readiness because `chroma_documents: 0` and get removed from the load balancer.
**Question:** Why would Chroma have zero documents on a fresh pod, and how do you fix the deployment?
**Answer:** In the current `main.py` lifespan, `ensure_indexed()` runs on startup — but only if `openai_api_key` or `embeddings_provider == "local"` is configured. If neither is set, indexing is skipped with a warning. Even when configured, a **race condition** occurs with multiple pods: concurrent `ensure_indexed()` calls on a shared Chroma volume can corrupt the index or leave a pod with zero readable documents.

The fundamental issue is that **indexing on pod startup is an anti-pattern** for K8s. `PRODUCTION_SCALING.md` recommends removing `ensure_indexed()` from lifespan and using a one-time init job or Celery worker instead. For readiness: a pod should check that the vector DB (local Chroma or remote Pinecone) has documents, but it shouldn't be responsible for creating them.

My fix plan: (1) run `scripts/reindex_chroma.py` as a K8s `Job` before rolling out API pods; (2) mount Chroma as ReadOnlyMany or switch to managed vector DB; (3) readiness checks remote DB count > 0 without writing; (4) liveness (`/health/live`) stays minimal — just process alive. Until then, ensure `OPENAI_API_KEY` or local embeddings are set and the `data/chroma` volume is pre-populated in the container image or init container.

**Key points:**
- Startup indexing skipped without API key or local embeddings
- Multi-pod concurrent indexing causes races on shared volume
- Move indexing to init job or async worker
- Readiness should verify, not create, index state

---

### Q22. Chroma Corruption with Multiple Docker Compose Replicas
**Scenario:** A developer scales the backend service to 3 replicas in Docker Compose with a shared `./data` volume. After a few hours, Chroma queries return garbage or crash.
**Question:** Why does this happen, and what's the correct deployment pattern?
**Answer:** ChromaDB persists to local disk at `data/chroma/` (SQLite-based under the hood). Docker Compose mounts `./data:/app/data` shared across backend replicas. Chroma is designed for **single-writer** access. Multiple uvicorn processes writing embeddings, appending documents, or calling `ensure_indexed()` concurrently on the same files cause file corruption and inconsistent reads.

The same risk applies to SQLite `app.db` — concurrent writes from multiple replicas will hit write locks or corrupt data. `PRODUCTION_SCALING.md` explicitly calls this out as a scaling constraint.

Correct patterns: (1) **single API replica** with local Chroma for dev/demo; (2) **PostgreSQL** for SQL + **managed vector DB** for embeddings (no shared filesystem); (3) if staying on Chroma temporarily, run exactly one writer pod and scale read replicas only (not supported natively by Chroma); (4) use an async worker for indexing that writes to Chroma when only one process is running.

For the interview, I'd articulate: shared volumes work for read-only complaint JSON, but not for Chroma or SQLite write workloads.

**Key points:**
- Chroma and SQLite are single-writer on local disk
- Shared `./data` volume across replicas causes corruption
- Use PostgreSQL + managed vector DB for multi-replica
- Only one process should write to Chroma at a time

---

### Q23. Switching from Uvicorn to Gunicorn
**Scenario:** You're updating `Dockerfile.backend` for production by replacing single uvicorn with gunicorn + 4 UvicornWorkers, as recommended in the scaling guide.
**Question:** What benefits and risks does this change introduce for this specific application?
**Answer:** Currently `Dockerfile.backend` runs a single uvicorn process. With gunicorn `-w 4 -k uvicorn.workers.UvicornWorker`, we get four worker processes handling requests concurrently. Benefits: auth/session routes (`/login`, `/me`) can serve ~4× throughput while one worker waits on an OpenAI LLM response; better CPU utilization on multi-core hosts; aligns with K8s "fewer workers per pod, more pods" pattern.

Risks specific to this codebase: (1) **Chroma singleton** — `get_chroma_store()` is a process-level singleton; four workers means four separate Chroma client instances reading the same files (OK for reads, dangerous for writes); (2) **in-memory Redis fallback** — each worker gets isolated cache if Redis is down; (3) **rate limiter race** — non-atomic counters undercount across workers; (4) **LLM blocking** — each worker can block on `chain.invoke()` for up to 120s (recommended gunicorn timeout).

Mitigations: require Redis, use PostgreSQL, avoid concurrent Chroma writes, set `--timeout 120` for slow `/ask`, and plan migration to managed vector DB before scaling workers heavily. In K8s, prefer 3 pods × 2 workers over 1 pod × 6 workers for blast-radius isolation.

**Key points:**
- 4 workers improve concurrent request handling
- Chroma/Redis fallback issues amplify per worker
- Set gunicorn timeout ≥ 120s for LLM latency
- Prefer more pods × fewer workers in K8s

---

### Q24. Week 1 Production Checklist Prioritization
**Scenario:** You're the tech lead launching Buiild Complaint RAG to an internal pilot with 200 users next week. You have three days of engineering time.
**Question:** What production hardening tasks do you prioritize from the scaling roadmap?
**Answer:** With three days, I'd focus on highest-ROI items from `PRODUCTION_SCALING.md` Week 1 list that prevent data loss and security incidents:

**Day 1 — Data layer:** Set `DATABASE_URL` to PostgreSQL. SQLite's write lock will break under 200 concurrent users doing registration, login, and chat message saves. Add connection pooling. Require Redis — modify `redis_client.py` to fail fast when `ENV=production` and Redis is unreachable, eliminating the in-memory fallback that causes random 401s behind a load balancer.

**Day 2 — Security + API:** Rotate `JWT_SECRET` via secrets manager (current default is `change-me-in-production`). Restrict `CORS_ORIGINS` to the frontend domain. Fix rate limiter to Redis `INCR`. Restrict `/reindex` to admin role via `RequireAdmin` in `rag.py` — currently any authenticated user can trigger a full reindex (DoS vector). Add `/health/live` and `/health/ready` split.

**Day 3 — Deployment:** Update `Dockerfile.backend` to gunicorn with 4 workers. Remove `ensure_indexed()` from startup; run `scripts/reindex_chroma.py` as a deploy init step. Run `scripts/benchmark_load.py --users 200 --concurrency 20` against staging to validate.

I'd defer Celery workers, managed vector DB, and streaming to week 2+. The pilot's risk profile is auth inconsistency, data corruption, and security defaults — not LLM latency optimization.

**Key points:**
- PostgreSQL + required Redis are top priorities
- Rotate JWT secret, restrict CORS, admin-only reindex
- Gunicorn multi-worker + health probe split
- Benchmark with 200 users before launch

---

## Testing & Evaluation

### Q25. Evaluation Notebook vs Production RAG Pipeline
**Scenario:** An interviewer asks about your LLM evaluation strategy and points to `notebooks/llm_evaluation_langchain_evals.ipynb`.
**Question:** What does the evaluation notebook test, and how does it differ from the production LangChain pipeline?
**Answer:** The notebook evaluates the **legacy TF-IDF RAG** in `src/complaint_rag.py` (used by Streamlit `app.py`), not the production LangChain + Chroma pipeline in `backend/app/rag_chain.py`. It builds a golden dataset of 5+ examples with `inputs.question` and `outputs.expected_topic` / `reference_answer`, wraps `ComplaintRAG.answer()` as `complaint_rag_target()`, and runs LangSmith `evaluate()` with `upload_results=False` (local, no API key needed).

Three **deterministic evaluators** are defined: `topic_keyword_evaluator` (checks if expected topic appears in answer), `retrieval_relevance_evaluator` (checks topic alias families in answer text), and `answer_length_evaluator` (20–500 words). Optional LLM-as-judge evaluators use OpenEvals (`exact_match`, `levenshtein_distance`) when `OPENAI_API_KEY` is set.

The evaluation **patterns** transfer to production: build golden set, define target function, run deterministic + LLM judges, analyze scorecard DataFrame. To evaluate production RAG, you'd swap the target to `get_rag_service().ask()` as shown in `PROJECT_GUIDE.md`. The notebook demonstrates the right methodology even though the underlying retriever differs (TF-IDF cosine similarity vs Chroma embedding search).

**Key points:**
- Notebook tests legacy TF-IDF `ComplaintRAG`, not LangChain pipeline
- Golden dataset + deterministic evaluators + LangSmith orchestration
- `upload_results=False` enables local eval without LangSmith API key
- Production eval: swap target function to `get_rag_service().ask()`

---

### Q26. Running Tests Without External Services
**Scenario:** A CI pipeline runs `pytest tests/ -v` on every pull request with no OpenAI API key, no Redis, and no pre-existing Chroma index.
**Question:** How does the test suite achieve isolation, and what coverage does it provide?
**Answer:** `tests/conftest.py` sets environment overrides before app import: `DB_PATH` to a temp SQLite file, `CHROMA_PERSIST_DIR` and `DATA_DIR` to temp directories, `REDIS_ENABLED=false` (forces `InMemoryStore`), `OPENAI_API_KEY=""`, and `RATE_LIMIT_ENABLED=false`. A `_reset_singletons()` fixture clears cached service instances between tests.

Coverage by module: `test_auth.py` — health, register, login, `/me`, logout, admin RBAC (403 for non-admin on `/users`); `test_sessions.py` — multi-device sessions, revoke, refresh; `test_rag.py` — `/ask` auth required, retrieval-only without OpenAI, template validation (422 for invalid), empty question rejection; `test_cache.py` — cache get/set, deterministic hashing, delete; `test_chroma.py` — demo dataset generation, JSON loading, graceful failure without OpenAI for indexing.

What's **not** covered: actual LLM response quality, OpenAI integration, Redis-specific behavior (atomic rate limits), concurrent load, or embedding cache effectiveness. The suite validates API contracts and business logic in isolation. I'd add integration tests with VCR-cached OpenAI responses for CI and a smoke test with real Redis in a nightly pipeline.

**Key points:**
- `conftest.py` isolates DB, Chroma, Redis, and OpenAI via env vars
- 5 test modules cover auth, sessions, RAG, cache, and Chroma
- Tests verify retrieval-only mode without OpenAI key
- Gaps: LLM quality, Redis concurrency, load testing

---

## Troubleshooting Scenarios

### Q27. CORS Errors in the Browser Console
**Scenario:** A developer runs the backend on port 8000 and the Vite frontend on port 3000. The browser console shows CORS policy errors when the frontend calls `http://localhost:8000/login` directly.
**Question:** Diagnose the CORS issue and explain the intended development setup.
**Answer:** The backend's CORS middleware in `main.py` allows origins from `CORS_ORIGINS` (default `["*"]` with `allow_credentials=True`). While wildcard origins with credentials can be problematic in some browsers, the real issue here is likely that the developer bypassed the **Vite dev proxy**.

The intended setup: `App.jsx` uses `const API_URL = '/api'`, and `vite.config.js` proxies `/api` → `http://127.0.0.1:8002` with path rewrite stripping `/api`. This means browser requests go to `localhost:3000/api/login` (same origin — no CORS), and Vite forwards to the backend.

Two common misconfigurations: (1) **port mismatch** — proxy targets 8002 but uvicorn runs on 8000; fix by aligning `vite.config.js` target; (2) **direct backend URL** — if someone changes `API_URL` to `http://localhost:8000`, cross-origin requests require proper CORS. Set `CORS_ORIGINS=http://localhost:3000` explicitly for this case.

For production, build the frontend (`npm run build`) and serve `dist/` behind nginx with `/api` proxied server-side — avoiding browser CORS entirely. The scaling guide recommends restricting `CORS_ORIGINS` to the production frontend domain.

**Key points:**
- Dev setup uses Vite `/api` proxy to avoid CORS
- Common bug: proxy port 8002 vs backend port 8000
- Production: nginx reverse proxy, not browser CORS
- Restrict `CORS_ORIGINS` in production

---

### Q28. Random 401 Errors After Horizontal Scaling
**Scenario:** After deploying 3 API replicas with Redis supposedly enabled, users report intermittent 401 "Invalid or expired session" errors — roughly 1 in 3 requests fail.
**Question:** What is the most likely root cause, and how do you diagnose it?
**Answer:** With 3 replicas and ~1/3 failure rate, the classic diagnosis is **session affinity failure with in-memory Redis fallback**. Check `/health` on each pod: if any show `"redis": "memory"` instead of `"redis": "redis"`, that pod has fallen back to `InMemoryStore` in `redis_client.py`. A user logs in on pod A (session stored in A's memory), next request hits pod B (no session → 401).

Diagnosis steps: (1) hit `/health` on each replica — compare `redis_available`; (2) check Redis connectivity from all pods (`REDIS_URL`, network policies, TLS); (3) verify `REDIS_ENABLED=true` in all environments; (4) check if Redis had brief outages causing fallback — the current code logs a warning but doesn't recover automatically to Redis mode without restart.

Fix: ensure all pods connect to the same Redis instance (ElastiCache/cluster), fail fast in production instead of in-memory fallback, and verify load balancer isn't pinning required (it shouldn't be — that's the point of shared Redis). Also check if the client is accidentally sending the JWT instead of session token, which could expire independently.

Secondary cause: non-atomic session rehydration race under high load, but the 1/3 pattern strongly suggests per-pod memory store.

**Key points:**
- 1/N failure rate ≈ N replicas with isolated in-memory sessions
- Check `/health` → `redis_available` on every pod
- In-memory fallback is per-process, not shared
- Production fix: require Redis, fail fast on connection loss

---

## Frontend & API Design

### Q29. Frontend Authentication Flow
**Scenario:** A frontend developer joins the team and needs to understand how the React app manages authentication state across page reloads.
**Question:** Walk through the authentication flow in the React Support Operations Console.
**Answer:** The SPA in `frontend/src/App.jsx` is a single component with state-driven views (no router library). On mount, a `useEffect` reads `localStorage.getItem('complaint-token')` into React state. If a token exists, it calls `GET /api/me` with `Authorization: Bearer {token}`. Success sets the user and navigates to dashboard; 401 clears the token from localStorage.

Login via `handleLogin()` POSTs to `/api/login` with email/password (pre-filled demo credentials). On success, it stores `data.token` (session token, not JWT) in localStorage under `complaint-token`, sets user state, and loads chats. All subsequent API calls use `authHeaders = { Authorization: \`Bearer ${token}\` }`.

Logout clears localStorage and resets state. The app does not implement token refresh automatically, though the backend supports `POST /sessions/refresh` to extend TTL. Session expiry after 24h (default) requires re-login unless refresh is wired up.

The Vite proxy (`/api` → backend) keeps all requests same-origin. Views include login, dashboard (static demo charts), assistant (RAG chat), knowledge (file upload), reports, and settings (shows health info).

**Key points:**
- Session token stored in `localStorage` as `complaint-token`
- Page reload restores session via `GET /me`
- JWT returned on login but not stored by frontend
- All API calls use Bearer auth header via `/api` proxy

---

### Q30. API Design for the /ask Endpoint
**Scenario:** You're reviewing the API design before an external team integrates with the complaint RAG platform programmatically.
**Question:** Critique the `POST /ask` endpoint design — what works well and what would you improve?
**Answer:** The current design in `routers/rag.py` and `schemas.py` is clean for an MVP. Strengths: (1) Pydantic validation — `question` min 1 char, `template` as enum (`support`/`manager`/`analyst`), optional `chat_id` for memory, `use_cache` default true; (2) response includes `answer`, `sources[]` for provenance, and `cached` boolean for observability; (3) rate limiting via dependency injection, not ad-hoc middleware; (4) auth required but role-agnostic — all roles can query.

Improvements for external/production API: (1) **async processing** — sync `chain.invoke()` blocks; return 202 + job ID for long queries, or stream via SSE (planned in scaling guide); (2) **cache control** — add `Cache-Control` headers or `corpus_version` to help clients reason about staleness; (3) **source detail** — return snippet previews or relevance scores, not just filenames; (4) **error taxonomy** — distinguish 429 (rate limit) vs 503 (OpenAI down) vs 400 (bad template); (5) **idempotency key** — for retry safety on timeouts; (6) **OpenAPI examples** — already auto-generated but could add more; (7) **admin audit** — log questions for compliance, especially with PII in complaints.

The thin router pattern (3 lines of business logic, delegate to `RAGChainService`) is good — integration changes happen in the service layer, not the HTTP handler.

**Key points:**
- Pydantic-validated request with template, chat_id, use_cache
- Response includes answer, sources, and cached flag
- Sync blocking is main production limitation
- Improvements: streaming, richer sources, error taxonomy, idempotency

---

## Quick Reference: Category & Difficulty Index

| Q# | Title | Category | Level |
|----|-------|----------|-------|
| Q1 | Explaining the Platform to a New Teammate | System Design | Junior |
| Q2 | Choosing FastAPI for the API Layer | System Design | Junior |
| Q3 | End-to-End Request Flow for a RAG Query | System Design | Mid |
| Q4 | Source of Truth for Complaint Data | System Design | Mid |
| Q5 | Scaling from MVP to 10,000 Concurrent Users | System Design | Senior |
| Q6 | How Retrieval Grounds the LLM Answer | RAG & LangChain | Junior |
| Q7 | Role-Specific Prompt Templates | RAG & LangChain | Mid |
| Q8 | Multi-Turn Conversation Context | RAG & LangChain | Mid |
| Q9 | Debugging RAG Quality with LangSmith | RAG & LangChain | Senior |
| Q10 | Operating Without an OpenAI API Key | RAG & LangChain | Junior |
| Q11 | Session Loss After Redis Restart | Auth & Redis | Junior |
| Q12 | JWT Bypasses Session Revocation | Auth & Redis | Mid |
| Q13 | Revoking a Compromised Session Across Devices | Auth & Redis | Mid |
| Q14 | Why Redis Is Mandatory for Multi-Replica Deployments | Auth & Redis | Senior |
| Q15 | Stale Answers After Uploading New Complaints | ChromaDB | Mid |
| Q16 | Document Structure in the Vector Index | ChromaDB | Junior |
| Q17 | Migrating from Local ChromaDB to a Managed Vector Database | ChromaDB | Senior |
| Q18 | Understanding RAG Cache Hits | Caching & Performance | Junior |
| Q19 | Rate Limit Exceeded During a Live Demo | Caching & Performance | Mid |
| Q20 | Low Cache Hit Ratio Despite Repeated FAQ Questions | Caching & Performance | Senior |
| Q21 | Kubernetes Readiness Probe Failing on Deploy | Production & DevOps | Senior |
| Q22 | Chroma Corruption with Multiple Docker Compose Replicas | Production & DevOps | Mid |
| Q23 | Switching from Uvicorn to Gunicorn | Production & DevOps | Mid |
| Q24 | Week 1 Production Checklist Prioritization | Production & DevOps | Senior |
| Q25 | Evaluation Notebook vs Production RAG Pipeline | Testing & Evaluation | Mid |
| Q26 | Running Tests Without External Services | Testing & Evaluation | Junior |
| Q27 | CORS Errors in the Browser Console | Troubleshooting | Mid |
| Q28 | Random 401 Errors After Horizontal Scaling | Troubleshooting | Senior |
| Q29 | Frontend Authentication Flow | Frontend & API | Junior |
| Q30 | API Design for the /ask Endpoint | Frontend & API | Mid |

---

*For deeper technical reference, see [PROJECT_GUIDE.md](./PROJECT_GUIDE.md), [ARCHITECTURE.md](./ARCHITECTURE.md), and [PRODUCTION_SCALING.md](./PRODUCTION_SCALING.md).*
