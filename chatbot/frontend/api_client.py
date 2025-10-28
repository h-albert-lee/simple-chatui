"""Client utilities for talking to the FastAPI backend."""

from __future__ import annotations

import json
from typing import Generator, Iterable

import requests

from chatbot.core.config import settings

_TIMEOUT = (10, 300)


def stream_chat_completion(messages: Iterable[dict[str, str]], model: str) -> Generator[str, None, None]:
    """Stream assistant responses from the backend."""

    payload = {
        "messages": list(messages),
        "model": model,
        "stream": True,
    }

    with requests.post(
        settings.BACKEND_API_URL,
        json=payload,
        stream=True,
        timeout=_TIMEOUT,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            if not line.startswith("data:"):
                continue
            data_str = line[len("data:") :].strip()
            if data_str == "[DONE]":
                break
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                # upstream might send plain text chunks; pass through
                yield data_str
                continue
            delta = (
                data.get("choices", [{}])[0]
                .get("delta", {})
                .get("content")
            )
            if delta:
                yield delta
