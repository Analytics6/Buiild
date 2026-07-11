from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import create_jwt_token, create_session
from ..dependencies import get_current_token, get_current_user
from ..schemas import LoginRequest, LoginResponse, MeResponse, RegisterRequest, RegisterResponse, StatusResponse, UserResponse
from ..sessions import get_session_service
from ..users import get_user_service

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest) -> RegisterResponse:
    try:
        user = get_user_service().register(
            email=str(payload.email),
            password=payload.password,
            full_name=payload.full_name,
            role=payload.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RegisterResponse(user=UserResponse(**user))


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request) -> LoginResponse:
    user = get_user_service().authenticate(str(payload.email), payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_session(
        user["id"],
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    jwt_token = create_jwt_token(user)
    return LoginResponse(
        token=token,
        jwt=jwt_token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
        ),
    )


@router.post("/logout", response_model=StatusResponse)
def logout(token: str = Depends(get_current_token)) -> StatusResponse:
    user = get_session_service().validate_session(token)
    if user:
        get_session_service().revoke_session(token, user_id=user["id"])
    return StatusResponse(status="logged_out")


@router.get("/me", response_model=MeResponse)
def me(user: dict = Depends(get_current_user)) -> MeResponse:
    return MeResponse(user=UserResponse(**user))
