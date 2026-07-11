from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class ComplaintRAG:
    def __init__(self, data_dir: str | Path | None = None, top_k: int = 5, records: List[Dict[str, Any]] | None = None):
        self.data_dir = Path(data_dir) if data_dir is not None else None
        self.top_k = top_k
        self.records: List[Dict[str, Any]] = []
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = None
        self._load_data(records=records)

    def _load_data(self, records: List[Dict[str, Any]] | None = None) -> None:
        rows: List[Dict[str, Any]] = []

        if records:
            rows = [
                {
                    "complaint": item.get("complaint") or item.get("issue") or item.get("description") or "",
                    "solution": item.get("solution") or item.get("resolution") or item.get("answer") or "",
                    "source": item.get("source", "inline"),
                }
                for item in records
                if item.get("complaint") or item.get("issue") or item.get("description")
            ]
        elif self.data_dir is not None:
            files = sorted(self.data_dir.glob("*.json"))
            if not files:
                raise FileNotFoundError(f"No JSON complaint files found in {self.data_dir}")

            for file_path in files:
                try:
                    with file_path.open("r", encoding="utf-8") as handle:
                        payload = json.load(handle)
                except Exception:
                    continue

                if isinstance(payload, dict):
                    payload = [payload]
                for item in payload:
                    complaint = item.get("complaint") or item.get("issue") or item.get("description") or ""
                    solution = item.get("solution") or item.get("resolution") or item.get("answer") or ""
                    if complaint:
                        rows.append({"complaint": complaint, "solution": solution, "source": file_path.name})
        else:
            raise ValueError("Either data_dir or records must be provided")

        self.records = rows
        if not self.records:
            raise ValueError("No complaint records were loaded")

        texts = [f"{r['complaint']} {r['solution']}" for r in self.records]
        self.matrix = self.vectorizer.fit_transform(texts)

    def search(self, query: str, top_k: int | None = None) -> List[Dict[str, Any]]:
        top_k = top_k or self.top_k
        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.matrix).ravel()
        top_idx = np.argsort(scores)[::-1][:top_k]

        return [
            {
                "complaint": self.records[idx]["complaint"],
                "solution": self.records[idx]["solution"],
                "source": self.records[idx]["source"],
                "score": float(scores[idx]),
            }
            for idx in top_idx
        ]

    def answer(self, question: str, top_k: int | None = None) -> Dict[str, Any]:
        matches = self.search(question, top_k=top_k)
        if not matches:
            return {"answer": "I could not find a closely related complaint in the dataset.", "sources": []}

        context = "\n\n".join(
            f"Complaint: {m['complaint']}\nSuggested solution: {m['solution']}"
            for m in matches
        )

        system_prompt = (
            "You are a customer support assistant. Use the retrieved complaint records to answer the user's question. "
            "If the records are insufficient, say so clearly."
        )

        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": f"Question: {question}\n\nRetrieved context:\n{context}",
                        },
                    ],
                    "temperature": 0.2,
                }
                response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=payload,
                    timeout=30,
                )
                if response.ok:
                    content = response.json()["choices"][0]["message"]["content"]
                    return {"answer": content, "sources": [m["source"] for m in matches]}
            except Exception:
                pass

        answer = (
            f"Based on the retrieved complaints, here is a concise response:\n\n"
            f"{context}"
        )
        return {"answer": answer, "sources": [m["source"] for m in matches]}


def build_demo_dataset(output_dir: str | Path, count: int = 200, force: bool = True) -> Path:
    from src.complaint_dataset import write_complaint_files

    return write_complaint_files(output_dir, count=count, force=force)
