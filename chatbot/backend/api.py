"""FastAPI routes for the chat backend."""

from __future__ import annotations

import json
import logging
from typing import Annotated, AsyncGenerator, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from chatbot.core import storage
from chatbot.core.config import settings

from .models import AuthRequest, AuthResponse, ChatCompletionRequest, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()
auth_router = APIRouter(prefix="/auth", tags=["auth"])


def _extract_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
        )
    return token.strip()


def get_current_user(
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> Dict[str, str]:
    token = _extract_token(authorization)
    user = storage.get_user_by_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return user


async def _stream_upstream(payload: Dict[str, object]) -> AsyncGenerator[bytes, None]:
    headers = {"Content-Type": "application/json"}
    if settings.UPSTREAM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.UPSTREAM_API_KEY}"

    base_url = str(settings.UPSTREAM_API_BASE).rstrip("/")
    url = f"{base_url}/v1/chat/completions"

    async with httpx.AsyncClient(timeout=None) as client:
        try:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for chunk in response.aiter_raw():
                    yield chunk
        except httpx.HTTPStatusError as exc:
            message = f"Upstream API returned {exc.response.status_code}"
            logger.error(message)
            error_payload = ErrorResponse(error=message).model_dump_json()
            yield f"data: {error_payload}\n\n".encode("utf-8")
        except httpx.RequestError as exc:  # network-level error
            message = f"Failed to reach upstream API: {exc}"
            logger.exception(message)
            error_payload = ErrorResponse(error=message).model_dump_json()
            yield f"data: {error_payload}\n\n".encode("utf-8")


@router.post("/chat/completions", response_class=StreamingResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    current_user: Dict[str, str] = Depends(get_current_user),
) -> StreamingResponse:
    """Proxy chat completion requests to the upstream API with streaming support."""

    if not request.messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The request must include at least one message.",
        )

    payload = request.model_dump(exclude_none=True)
    payload.setdefault("model", settings.DEFAULT_MODEL)
    payload["stream"] = True

    logger.debug("Forwarding payload to upstream: %s", json.dumps(payload))

    return StreamingResponse(
        _stream_upstream(payload),
        media_type="text/event-stream",
    )


@auth_router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: AuthRequest) -> AuthResponse:
    try:
        user_id = storage.create_user(payload.username, payload.password)
    except storage.UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    token = storage.issue_token(user_id)
    return AuthResponse(user_id=user_id, username=payload.username, token=token)


@auth_router.post("/login", response_model=AuthResponse)
def login(payload: AuthRequest) -> AuthResponse:
    user = storage.authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = storage.issue_token(user["id"])
    return AuthResponse(user_id=user["id"], username=user["username"], token=token)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
) -> Response:
    token = _extract_token(authorization)
    storage.revoke_token(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


router.include_router(auth_router)
