import json
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..chroma_store import get_chroma_store, load_documents_from_json
from ..config import get_settings
from ..dependencies import get_current_user, rate_limit
from ..rag_chain import get_rag_service
from ..schemas import AskRequest, AskResponse, ReindexResponse, TemplatesResponse, UploadResponse

router = APIRouter(tags=["rag"])


@router.get("/templates", response_model=TemplatesResponse)
def list_templates() -> TemplatesResponse:
    return TemplatesResponse(templates=get_rag_service().list_templates())


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, user: dict = Depends(rate_limit("ask"))) -> AskResponse:
    try:
        result = get_rag_service().ask(
            question=payload.question.strip(),
            template=payload.template,
            chat_id=payload.chat_id,
            use_cache=payload.use_cache,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AskResponse(**result)


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...), user: dict = Depends(get_current_user)) -> UploadResponse:
    settings = get_settings()
    content = await file.read()
    try:
        payload = json.loads(content.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail="JSON must be a list or object")

    target_dir = settings.data_dir / file.filename.replace(".json", "")
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = target_dir / "custom.json"
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    indexed = get_chroma_store().add_documents_from_payload(payload, source=file.filename)
    return UploadResponse(status="uploaded", path=str(out_path), indexed_documents=indexed)


@router.post("/reindex", response_model=ReindexResponse)
def reindex(user: dict = Depends(get_current_user)) -> ReindexResponse:
    settings = get_settings()
    docs = load_documents_from_json(settings.data_dir)
    count = get_chroma_store().index_documents(docs, replace=True)
    return ReindexResponse(status="reindexed", document_count=count)
