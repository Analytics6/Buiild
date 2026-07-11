import json


def test_build_demo_dataset():
    from backend.app.chroma_store import build_demo_dataset

    records = build_demo_dataset(count=5)
    assert len(records) == 5
    assert "complaint" in records[0]
    assert "solution" in records[0]


def test_load_documents_from_json(test_env):
    from backend.app.chroma_store import load_documents_from_json, seed_demo_data

    data_path = test_env["data_path"]
    seed_demo_data(data_path)
    docs = load_documents_from_json(data_path)
    assert len(docs) == 200
    assert "Complaint:" in docs[0].page_content


def test_load_custom_json(test_env):
    from backend.app.chroma_store import load_documents_from_json

    data_path = test_env["data_path"]
    custom = data_path / "custom.json"
    custom.write_text(
        json.dumps([{"complaint": "billing issue with overcharge", "solution": "issued refund"}]),
        encoding="utf-8",
    )
    docs = load_documents_from_json(data_path)
    assert any("billing" in doc.page_content.lower() for doc in docs)


def test_chroma_document_count_without_openai(test_env):
    from backend.app.chroma_store import get_chroma_store

    store = get_chroma_store()
    try:
        store.ensure_indexed()
    except ValueError as exc:
        assert "OPENAI_API_KEY" in str(exc)
