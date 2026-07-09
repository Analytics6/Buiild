from pathlib import Path

from src.complaint_rag import ComplaintRAG, build_demo_dataset


def test_retrieval_returns_relevant_complaint(tmp_path: Path):
    build_demo_dataset(tmp_path, count=10)
    rag = ComplaintRAG(tmp_path, top_k=3)

    results = rag.search("billing issue", top_k=3)

    assert len(results) == 3
    assert any("billing" in item["complaint"].lower() for item in results)


def test_can_initialize_with_inline_records():
    rag = ComplaintRAG(data_dir=None, records=[{"complaint": "custom billing issue", "solution": "refund the charge"}], top_k=1)

    assert len(rag.records) == 1
    assert rag.records[0]["complaint"] == "custom billing issue"
