"""Auth request/response schemas."""

from pydantic import BaseModel


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    usernameOrEmail: str
    password: str


class GoogleLoginRequest(BaseModel):
    idToken: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    hasGoogle: bool
    createdAt: str


class AuthResponse(BaseModel):
    user: UserResponse
