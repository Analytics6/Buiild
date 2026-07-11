from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db
from ..dependencies import get_current_user
from ..schemas import ChatCreateRequest, ChatResponse, MessageCreateRequest, MessageResponse, StatusResponse

router = APIRouter(tags=["chats"])


@router.get("/chats", response_model=list[ChatResponse])
def chats(user: dict = Depends(get_current_user)) -> list[ChatResponse]:
    rows = get_db().fetchall("SELECT * FROM chats WHERE user_id = ? ORDER BY id DESC", (user["id"],))
    return [
        ChatResponse(
            id=row["id"],
            title=row["title"],
            user_id=row["user_id"],
            created_at=str(row.get("created_at")) if row.get("created_at") else None,
        )
        for row in rows
    ]


@router.post("/chat", response_model=ChatResponse)
def create_chat(payload: ChatCreateRequest, user: dict = Depends(get_current_user)) -> ChatResponse:
    chat_id = get_db().insert(
        "INSERT INTO chats (user_id, title) VALUES (?, ?)",
        (user["id"], payload.title),
    )
    return ChatResponse(id=chat_id, title=payload.title)


@router.get("/chat/{chat_id}/messages", response_model=list[MessageResponse])
def get_messages(chat_id: int, user: dict = Depends(get_current_user)) -> list[MessageResponse]:
    chat = get_db().fetchone("SELECT * FROM chats WHERE id = ? AND user_id = ?", (chat_id, user["id"]))
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    rows = get_db().fetchall("SELECT * FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,))
    return [
        MessageResponse(
            id=row["id"],
            chat_id=row["chat_id"],
            role=row["role"],
            content=row["content"],
            created_at=str(row.get("created_at")) if row.get("created_at") else None,
        )
        for row in rows
    ]


@router.post("/chat/{chat_id}/message", response_model=StatusResponse)
def save_message(chat_id: int, payload: MessageCreateRequest, user: dict = Depends(get_current_user)) -> StatusResponse:
    chat = get_db().fetchone("SELECT * FROM chats WHERE id = ? AND user_id = ?", (chat_id, user["id"]))
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    get_db().execute(
        "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
        (chat_id, payload.role, payload.content),
    )
    return StatusResponse(status="saved")


@router.delete("/chat/{chat_id}")
def delete_chat(chat_id: int, user: dict = Depends(get_current_user)) -> dict:
    chat = get_db().fetchone("SELECT * FROM chats WHERE id = ? AND user_id = ?", (chat_id, user["id"]))
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    get_db().execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    get_db().execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    return {"status": "deleted", "chat_id": chat_id}
