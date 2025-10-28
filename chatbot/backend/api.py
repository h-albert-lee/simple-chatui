"""FastAPI routes for the chat backend."""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator, Dict

import httpx
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from chatbot.core.config import settings

from .models import ChatCompletionRequest, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()


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
async def chat_completions(request: ChatCompletionRequest) -> StreamingResponse:
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
