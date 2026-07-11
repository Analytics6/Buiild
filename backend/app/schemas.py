from typing import Any, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


RoleType = Literal["admin", "manager", "analyst", "support"]
TemplateType = Literal["support", "manager", "analyst"]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=1)
    role: RoleType = "analyst"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class LoginResponse(BaseModel):
    token: str
    jwt: str
    user: UserResponse


class RegisterResponse(BaseModel):
    user: UserResponse


class MeResponse(BaseModel):
    user: UserResponse


class StatusResponse(BaseModel):
    status: str


class SessionInfo(BaseModel):
    id: Optional[int] = None
    token_preview: str
    created_at: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None


class SessionsResponse(BaseModel):
    sessions: list[SessionInfo]


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    template: TemplateType = "support"
    chat_id: Optional[int] = None
    use_cache: bool = True


class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    cached: bool = False


class UploadResponse(BaseModel):
    status: str
    path: str
    indexed_documents: int


class TemplatesResponse(BaseModel):
    templates: list[str]


class HealthResponse(BaseModel):
    status: str
    redis: str
    redis_available: bool
    database: str
    chroma_collection: str
    chroma_documents: int
    openai_configured: bool


class ChatCreateRequest(BaseModel):
    title: str = "New conversation"


class ChatResponse(BaseModel):
    id: int
    title: str
    user_id: Optional[int] = None
    created_at: Optional[str] = None


class MessageCreateRequest(BaseModel):
    role: str = "assistant"
    content: str = ""


class MessageResponse(BaseModel):
    id: Optional[int] = None
    chat_id: Optional[int] = None
    role: str
    content: str
    created_at: Optional[str] = None


class UserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, min_length=1)
    role: Optional[RoleType] = None
    password: Optional[str] = Field(default=None, min_length=6)
    is_active: Optional[bool] = None


class UsersListResponse(BaseModel):
    users: list[UserResponse]


class UserDetailResponse(BaseModel):
    user: UserResponse


class ReindexResponse(BaseModel):
    status: str
    document_count: int


class ErrorResponse(BaseModel):
    detail: str
