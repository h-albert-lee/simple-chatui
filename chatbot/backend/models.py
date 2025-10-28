"""Pydantic models for the backend API."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, constr


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    messages: list[ChatMessage]
    model: Optional[str] = None
    stream: bool = True
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ErrorResponse(BaseModel):
    error: str


class AuthRequest(BaseModel):
    username: constr(min_length=1)
    password: constr(min_length=1)


class AuthResponse(BaseModel):
    user_id: str
    username: str
    token: str
