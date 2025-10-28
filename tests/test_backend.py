import json
import sys
from importlib import reload

import httpx
from httpx import ASGITransport
import pytest
import respx


@pytest.fixture(autouse=True)
def reload_modules(monkeypatch, tmp_path):
    monkeypatch.setenv("UPSTREAM_API_BASE", "http://upstream.test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path/'backend.db'}")
    monkeypatch.setenv("BACKEND_API_URL", "http://localhost:8000/api/v1/chat/completions")

    from chatbot.core import config
    reload(config)
    sys.modules["chatbot.core.config"] = config

    from chatbot.backend import api, main
    reload(api)
    reload(main)
    sys.modules["chatbot.backend.api"] = api
    sys.modules["chatbot.backend.main"] = main

    from chatbot.core import storage

    storage.initialize_database()
    yield


@pytest.mark.asyncio
async def test_chat_completions_stream():
    from chatbot.backend.main import app

    from chatbot.core import storage

    user_id = storage.create_user("tester", "secret")
    token = storage.issue_token(user_id)

    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.post("http://upstream.test/v1/chat/completions").mock(
            return_value=httpx.Response(
                status_code=200,
                text=(
                    "data: {\"choices\": [{\"delta\": {\"content\": \"Hello\"}}]}\n\n"
                    "data: [DONE]\n\n"
                ),
                headers={"Content-Type": "text/event-stream"},
            )
        )

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hi"}]},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            body = "".join([chunk async for chunk in response.aiter_text()])

        assert "Hello" in body
        assert route.called
        upstream_request = route.calls.last.request
        payload = json.loads(upstream_request.content.decode("utf-8"))
        assert payload["model"]  # default model injected
        assert payload["stream"] is True
