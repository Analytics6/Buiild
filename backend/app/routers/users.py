from fastapi import APIRouter, HTTPException

from ..dependencies import RequireAdmin
from ..schemas import UserDetailResponse, UserResponse, UsersListResponse, UserUpdateRequest
from ..users import get_user_service

router = APIRouter(tags=["users"])


@router.get("/users", response_model=UsersListResponse)
def list_users(admin: RequireAdmin) -> UsersListResponse:
    return UsersListResponse(users=[UserResponse(**u) for u in get_user_service().list_users()])


@router.get("/users/{user_id}", response_model=UserDetailResponse)
def get_user(user_id: int, admin: RequireAdmin) -> UserDetailResponse:
    user = get_user_service().get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserDetailResponse(user=UserResponse(**user))


@router.put("/users/{user_id}", response_model=UserDetailResponse)
def update_user(user_id: int, payload: UserUpdateRequest, admin: RequireAdmin) -> UserDetailResponse:
    try:
        user = get_user_service().update_user(
            user_id,
            email=str(payload.email) if payload.email else None,
            full_name=payload.full_name,
            role=payload.role,
            password=payload.password,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserDetailResponse(user=UserResponse(**user))


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: RequireAdmin) -> dict:
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    if not get_user_service().delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted", "user_id": user_id}
