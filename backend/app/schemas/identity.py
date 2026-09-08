from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str


class OrganizationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str


class MembershipPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    organization_id: str
    user_id: str


class MemberPublic(BaseModel):
    membership_id: str
    role: str
    user: UserPublic


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    organization_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
    organization: OrganizationPublic
    membership: MembershipPublic


class MeResponse(BaseModel):
    user: UserPublic
    organization: OrganizationPublic
    membership: MembershipPublic
