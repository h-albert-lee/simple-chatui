"""Client utilities for talking to the FastAPI backend."""

from __future__ import annotations

import json
from typing import Dict, Generator, Iterable

import requests

from chatbot.core.config import settings

_TIMEOUT = (10, 300)


def _get_base_url() -> str:
    return settings.BACKEND_API_URL.rsplit("/", 1)[0]


def stream_chat_completion(
    messages: Iterable[dict[str, str]], *, model: str, token: str
) -> Generator[str, None, None]:
    """Stream assistant responses from the backend."""

    payload = {
        "messages": list(messages),
        "model": model,
        "stream": True,
    }

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with requests.post(
        settings.BACKEND_API_URL,
        json=payload,
        headers=headers,
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


def signup(username: str, password: str) -> Dict[str, str]:
    response = requests.post(
        f"{_get_base_url()}/auth/signup",
        json={"username": username, "password": password},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def login(username: str, password: str) -> Dict[str, str]:
    response = requests.post(
        f"{_get_base_url()}/auth/login",
        json={"username": username, "password": password},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def logout(token: str) -> None:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    requests.post(
        f"{_get_base_url()}/auth/logout",
        headers=headers,
        timeout=_TIMEOUT,
    ).raise_for_status()
