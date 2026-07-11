# Buiild Complaint RAG

Local RAG prototype for complaint handling: ingest, search, and draft responses.

## Quick Start (Local)

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env     # add OPENAI_API_KEY
python scripts/ingest.py
python scripts/run_api.py
```

API: http://127.0.0.1:8000 — Docs: http://127.0.0.1:8000/docs

## Quick Start (Docker)

```bash
copy .env.example .env
docker compose up --build
```

## Project Layout

| Path | Purpose |
|------|---------|
| `src/` | Core RAG pipeline, API, agentic demo |
| `scripts/` | CLI: ingest, run API, evaluate |
| `frontend/` | React dashboard |
| `notebooks/` | LLM evaluation notebooks |
| `tests/` | Pytest suite |
| `docs/` | Architecture and scaling guides |

## Evaluation

- **Notebook:** `notebooks/llm_evaluation_langchain_evals.ipynb` — LangChain evaluators (correctness, faithfulness, relevance)
- **CLI:** `python scripts/evaluate.py --dataset data/eval_dataset.json --output results/eval_report.json`
- **API:** `POST /evaluate` with `{"dataset_path": "data/eval_dataset.json"}`

## Development

- **Lint:** `ruff check src/ scripts/ tests/`
- **Format:** `ruff format src/ scripts/ tests/`
- **Type check:** `mypy src/`

## Testing

- Unit and API tests under `tests/` (ingestion, chunking, embeddings, vector store, retrieval, generation, agentic flow, FastAPI routes).
- Run locally after `pip install -r requirements.txt`:

```bash
pytest tests/ -v
```

## Documentation

- [Project Guide](docs/PROJECT_GUIDE.md) — main guide for setup, workflows, and project overview
- [Architecture](docs/ARCHITECTURE.md) — system design and component layout
- [Production Scaling](docs/PRODUCTION_SCALING.md) — deployment and scaling guidance
- [Interview Questions](docs/INTERVIEW_QUESTIONS.md) — interview prep with 30 scenario-based Q&As
