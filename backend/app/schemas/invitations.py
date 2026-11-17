from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InvitationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    role: Literal["ADMIN", "MEMBER"]


class InvitationStatusResponse(BaseModel):
    status: Literal["accepted"]


class InvitationPublic(BaseModel):
    id: str
    email: str
    role: str
    expires_at: datetime
    created_at: datetime


class InvitationAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=512)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class InvitationAcceptedResponse(BaseModel):
    status: Literal["accepted"]
    organization_id: str


class InvitationSignInResponse(BaseModel):
    status: Literal["sign_in_required"]


class UserOrganizationPublic(BaseModel):
    organization_id: str
    name: str
    role: str
    membership_id: str


class ActiveOrganizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: str = Field(min_length=1, max_length=36)
