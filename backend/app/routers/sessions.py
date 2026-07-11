from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_current_token, get_current_user
from ..schemas import SessionsResponse, SessionInfo, StatusResponse
from ..sessions import get_session_service

router = APIRouter(tags=["sessions"])


@router.get("/sessions", response_model=SessionsResponse)
def list_sessions(user: dict = Depends(get_current_user)) -> SessionsResponse:
    sessions = get_session_service().list_sessions(user["id"])
    return SessionsResponse(
        sessions=[
            SessionInfo(
                id=s.get("id"),
                token_preview=s["token_preview"],
                created_at=s.get("created_at"),
                user_agent=s.get("user_agent"),
                ip_address=s.get("ip_address"),
            )
            for s in sessions
        ]
    )


@router.delete("/sessions/{session_id}", response_model=StatusResponse)
def revoke_session(session_id: int, user: dict = Depends(get_current_user)) -> StatusResponse:
    sessions = get_session_service().list_sessions(user["id"])
    target = next((s for s in sessions if s.get("id") == session_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Session not found")
    get_session_service().revoke_session(target["token"], user_id=user["id"])
    return StatusResponse(status="revoked")


@router.post("/sessions/refresh", response_model=StatusResponse)
def refresh_session(user: dict = Depends(get_current_user), token: str = Depends(get_current_token)) -> StatusResponse:
    if not get_session_service().refresh_session(token):
        raise HTTPException(status_code=404, detail="Session not found")
    return StatusResponse(status="refreshed")
