import json
import os
from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_core.documents import Document

app = FastAPI(title="Complaint RAG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "complaints"
DATA_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_TEMPLATES = {
    "support": PromptTemplate.from_template(
        "You are a customer support assistant. Use the retrieved complaint records to answer the user's question.\nQuestion: {question}\nContext:\n{context}\nAnswer in a concise and empathetic tone."
    ),
    "manager": PromptTemplate.from_template(
        "You are a support operations manager. Summarize the likely resolution strategy for the complaint and highlight the operational takeaway.\nQuestion: {question}\nContext:\n{context}\nProvide a short executive summary."
    ),
    "analyst": PromptTemplate.from_template(
        "You are a complaint analysis specialist. Compare the retrieved complaints and explain the recurring resolution pattern.\nQuestion: {question}\nContext:\n{context}\nGive a concise analytical summary."
    ),
}


def build_demo_dataset(count: int = 200) -> List[Dict[str, Any]]:
    topics = [
        ("billing", "billing issue", "refund", "The customer was overcharged and received a refund after a review of the invoice history."),
        ("delivery", "delivery delay", "replacement", "The shipment was resent at no extra cost and the customer received proactive tracking updates."),
        ("product", "defective product", "replacement", "The product was replaced under warranty and the customer was offered a prepaid return label."),
        ("subscription", "subscription cancellation", "credit", "The account was canceled and a service credit was applied for the inconvenience caused by the billing confusion."),
        ("support", "slow support response", "priority", "The case was escalated to a priority support queue and the customer received a follow-up call within one business day."),
        ("refund", "refund request", "processing", "The refund was processed within five business days and the customer was informed of the transaction timeline."),
    ]
    records = []
    for i in range(count):
        topic, complaint_seed, solution_seed, solution_text = topics[i % len(topics)]
        complaint = (
            f"A customer contacted support about a {complaint_seed} involving the {topic} experience. "
            f"They explained that the problem had already caused frustration because it affected their account, order, or service expectations. "
            f"The customer described repeated attempts to resolve the issue, uncertainty about the next step, and a strong expectation that the company would provide a clear explanation and a fair remedy."
        )
        solution = (
            f"Support investigated the case carefully and resolved it with {solution_seed}. "
            f"The team documented the timeline, explained the action taken to the customer, and confirmed the outcome in writing. "
            f"{solution_text}"
        )
        records.append({"complaint": complaint, "solution": solution})
    return records


def seed_demo_data() -> None:
    if not any(DATA_DIR.glob("*.json")):
        for idx, record in enumerate(build_demo_dataset(200)):
            path = DATA_DIR / f"complaint_{idx + 1:03d}.json"
            with path.open("w", encoding="utf-8") as handle:
                json.dump(record, handle, indent=2)


def load_documents() -> List[Document]:
    seed_demo_data()
    docs: List[Document] = []
    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            continue
        if isinstance(payload, dict):
            payload = [payload]
        for item in payload:
            complaint = item.get("complaint") or item.get("issue") or item.get("description") or ""
            solution = item.get("solution") or item.get("resolution") or item.get("answer") or ""
            if complaint:
                docs.append(Document(page_content=f"Complaint: {complaint}\nSolution: {solution}", metadata={"source": path.name}))
    return docs


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/templates")
def list_templates() -> Dict[str, List[str]]:
    return {"templates": list(PROMPT_TEMPLATES.keys())}


@app.post("/ask")
def ask(question: str, template: str = "support") -> Dict[str, Any]:
    if template not in PROMPT_TEMPLATES:
        raise HTTPException(status_code=400, detail="Invalid template")

    docs = load_documents()
    if not docs:
        raise HTTPException(status_code=404, detail="No complaint documents found")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "answer": "OpenAI API key is not configured. Add OPENAI_API_KEY to use the LLM-powered answer.",
            "sources": [doc.metadata["source"] for doc in docs[:3]],
        }

    embeddings = OpenAIEmbeddings(openai_api_key=api_key)
    vector_store = FAISS.from_documents(docs, embeddings)
    retriever = vector_store.as_retriever(search_kwargs={"k": 5})
    relevant_docs = retriever.get_relevant_documents(question)

    context = "\n\n".join(doc.page_content for doc in relevant_docs)
    prompt = PROMPT_TEMPLATES[template]
    llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=api_key, temperature=0.2)
    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke({"question": question, "context": context})

    return {"answer": answer, "sources": [doc.metadata["source"] for doc in relevant_docs]}


@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> Dict[str, Any]:
    content = await file.read()
    try:
        payload = json.loads(content.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail="JSON must be a list or object")

    target_dir = DATA_DIR / file.filename.replace(".json", "")
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / "custom.json"
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    return {"status": "uploaded", "path": str(out_path)}
