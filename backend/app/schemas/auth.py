import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique device identifier of the mobile installation",
    )

    @field_validator("device_id")
    @classmethod
    def normalize_and_validate_device_id(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("device_id cannot be blank or whitespace-only")
        if len(stripped) > 128:
            raise ValueError("device_id length cannot exceed 128 characters")
        return stripped


class CreateChallengeResponse(BaseModel):
    challenge_id: uuid.UUID
    code: str
    login_url: str
    expires_in: int
    expires_at: datetime


class ChallengeStatusResponse(BaseModel):
    status: str
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
    expires_in: int | None = None


class RefreshTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(..., min_length=1, description="Opaque refresh token")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(..., min_length=1, description="Opaque refresh token to revoke")


class LogoutResponse(BaseModel):
    status: str = "ok"
