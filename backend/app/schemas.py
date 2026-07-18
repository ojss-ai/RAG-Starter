import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: Literal["admin", "user"] = "user"


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ApiKeyOut(BaseModel):
    id: int
    name: str
    scope: str
    revoked_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreated(BaseModel):
    id: int
    name: str
    scope: str
    api_key: str  # plaintext — returned exactly once at creation


class AuditOut(BaseModel):
    id: int
    actor: str
    action: str
    target: str
    detail: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadedDoc(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    duplicate: bool = False


class UploadResponse(BaseModel):
    documents: list[UploadedDoc]
    rejected: list[str]

class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    error: str | None
    size_bytes: int
    partition_key: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentList(BaseModel):
    total: int
    documents: list[DocumentOut]


class MetricsOut(BaseModel):
    documents_by_status: dict[str, int]
    documents_total: int
    chunks_total: int
    vector_backend: str
    vectors_total: int
    http_requests: int
    http_errors: int
    error_rate: float
